# -*- coding: utf-8 -*-
'''
The function in `vdirsyncer.sync` can be called on two instances of `Storage`
to synchronize them. Due to the abstract API storage classes are implementing,
the two given instances don't have to be of the same exact type. This allows us
not only to synchronize a local vdir with a CalDAV server, but also synchronize
two CalDAV servers or two local vdirs.

The algorithm is based on the blogpost "How OfflineIMAP works" by Edward Z.
Yang. http://blog.ezyang.com/2012/08/how-offlineimap-works/
'''
import contextlib
import itertools
import logging

from . import exceptions
from .utils import uniq

sync_logger = logging.getLogger(__name__)


class SyncError(exceptions.Error):
    '''Errors related to synchronization.'''


class SyncConflict(SyncError):
    '''
    Two items changed since the last sync, they now have different contents and
    no conflict resolution method was given.

    :param ident: The ident of the item.
    :param href_a: The item's href on side A.
    :param href_b: The item's href on side B.
    '''

    ident = None
    href_a = None
    href_b = None


class IdentConflict(SyncError):
    '''
    Multiple items on the same storage have the same UID.

    :param storage: The affected storage.
    :param hrefs: List of affected hrefs on `storage`.
    '''
    storage = None
    _hrefs = None

    @property
    def hrefs(self):
        return self._hrefs

    @hrefs.setter
    def hrefs(self, val):
        new_val = set(val)
        assert len(new_val) > 1, val
        self._hrefs = new_val


class StorageEmpty(SyncError):
    '''
    One storage unexpectedly got completely empty between two synchronizations.
    The first argument is the empty storage.

    :param empty_storage: The empty
        :py:class:`vdirsyncer.storage.base.Storage`.
    '''

    empty_storage = None


class BothReadOnly(SyncError):
    '''
    Both storages are marked as read-only. Synchronization is therefore not
    possible.
    '''


class PartialSync(SyncError):
    '''
    Attempted change on read-only storage.
    '''
    storage = None


class _StorageInfo(object):
    '''A wrapper class that holds prefetched items, the status and other
    things.'''
    def __init__(self, storage, status):
        '''
        :param status: {ident: {'href': href, 'etag': etag}}
        '''
        self.storage = storage

        #: Represents the status as given. Must not be modified.
        self.status = status

        #: Represents the current state of the storage and is modified as items
        #: are uploaded and downloaded. Will be dumped into status.
        self.new_status = None

    def prepare_new_status(self):
        href_to_status = dict((meta['href'], (ident, meta))
                              for ident, meta
                              in self.status.items())

        prefetch = []
        self.new_status = {}

        def _store_props(ident, props):
            new_props = self.new_status.setdefault(ident, props)
            if new_props is not props:
                raise IdentConflict(storage=self.storage,
                                    hrefs=[new_props['href'],
                                           props['href']])

        for href, etag in self.storage.list():
            ident, old_meta = href_to_status.get(href, (None, None))
            meta = dict(old_meta) if old_meta is not None else {}
            meta['href'] = href
            meta['etag'] = etag
            assert etag is not None
            if meta != old_meta:
                # Either the item is completely new, or updated
                # In both cases we should prefetch
                prefetch.append(href)
            else:
                _store_props(ident, meta)

        # Prefetch items
        for href, item, etag in (self.storage.get_multi(prefetch)
                                 if prefetch else ()):
            meta = {
                'href': href,
                'etag': etag,
                'item': item,
                'hash': item.hash,
            }
            _store_props(item.ident, meta)

    def is_changed(self, ident):
        status = self.status.get(ident, None)
        meta = self.new_status[ident]

        if status is None:  # new item
            return True

        if meta['etag'] != status['etag']:  # etag changed
            old_hash = status.get('hash')
            if old_hash is None or meta['item'].hash != old_hash:
                # item actually changed
                return True
            else:
                # only etag changed
                return False


def _status_migrate(status):
    for ident in list(status):
        value = status[ident]
        if len(value) == 4:
            href_a, etag_a, href_b, etag_b = value

            status[ident] = ({
                'href': href_a,
                'etag': etag_a,
            }, {
                'href': href_b,
                'etag': etag_b,
            })
        elif len(value) == 2:
            a, b = value
            a.setdefault('hash', '')
            b.setdefault('hash', '')


def _compress_meta(meta):
    '''Make in-memory metadata suitable for disk storage by removing fetched
    item content'''
    if set(meta) == {'href', 'etag', 'hash'}:
        return meta

    return {
        'href': meta['href'],
        'etag': meta['etag'],
        'hash': meta['hash']
    }


def sync(storage_a, storage_b, status, conflict_resolution=None,
         force_delete=False, error_callback=None, partial_sync='revert'):
    '''Synchronizes two storages.

    :param storage_a: The first storage
    :type storage_a: :class:`vdirsyncer.storage.base.Storage`
    :param storage_b: The second storage
    :type storage_b: :class:`vdirsyncer.storage.base.Storage`
    :param status: {ident: (href_a, etag_a, href_b, etag_b)}
        metadata about the two storages for detection of changes. Will be
        modified by the function and should be passed to it at the next sync.
        If this is the first sync, an empty dictionary should be provided.
    :param conflict_resolution: A function that, given two conflicting item
        versions A and B, returns a new item with conflicts resolved. The UID
        must be the same. The strings `"a wins"` and `"b wins"` are also
        accepted to mean that that side's version will always be taken. If none
        is provided, the sync function will raise :py:exc:`SyncConflict`.
    :param force_delete: When one storage got completely emptied between two
        syncs, :py:exc:`StorageEmpty` is raised for
        safety. Setting this parameter to ``True`` disables this safety
        measure.
    :param error_callback: Instead of raising errors when executing actions,
        call the given function with an `Exception` as the only argument.
    :param partial_sync: What to do when doing sync actions on read-only
        storages.

        - ``error``: Raise an error.
        - ``ignore``: Those actions are simply skipped.
        - ``revert`` (default): Revert changes on other side.
    '''
    if storage_a.read_only and storage_b.read_only:
        raise BothReadOnly()

    if conflict_resolution == 'a wins':
        conflict_resolution = lambda a, b: a
    elif conflict_resolution == 'b wins':
        conflict_resolution = lambda a, b: b

    _status_migrate(status)

    a_status = {}
    b_status = {}
    for ident, (meta_a, meta_b) in status.items():
        a_status[ident] = meta_a
        b_status[ident] = meta_b

    a_info = _StorageInfo(storage_a, a_status)
    b_info = _StorageInfo(storage_b, b_status)

    a_info.prepare_new_status()
    b_info.prepare_new_status()

    if status and not force_delete:
        if a_info.new_status and not b_info.new_status:
            raise StorageEmpty(empty_storage=storage_b)
        elif b_info.new_status and not a_info.new_status:
            raise StorageEmpty(empty_storage=storage_a)

    actions = list(_get_actions(a_info, b_info))

    with storage_a.at_once(), storage_b.at_once():
        for action in actions:
            try:
                action.run(a_info, b_info, conflict_resolution, partial_sync)
            except Exception as e:
                if error_callback:
                    error_callback(e)
                else:
                    raise

    status.clear()
    for ident in uniq(itertools.chain(a_info.new_status,
                                      b_info.new_status)):
        status[ident] = (
            _compress_meta(a_info.new_status[ident]),
            _compress_meta(b_info.new_status[ident])
        )


class Action:
    def _run_impl(self, a, b):
        raise NotImplementedError()

    def run(self, a, b, conflict_resolution, partial_sync):
        with self.auto_rollback(a, b):
            if self.dest.storage.read_only:
                if partial_sync == 'error':
                    raise PartialSync(self.dest.storage)
                elif partial_sync == 'ignore':
                    self.rollback(a, b)
                    return
                else:
                    assert partial_sync == 'revert'

            self._run_impl(a, b)

    @contextlib.contextmanager
    def auto_rollback(self, a, b):
        try:
            yield
        except BaseException as e:
            self.rollback(a, b)
            raise e

    def rollback(self, a, b):
        for info in (a, b):
            if self.ident in info.status:
                info.new_status[self.ident] = info.status[self.ident]
            else:
                info.new_status.pop(self.ident, None)


class Upload(Action):
    def __init__(self, item, dest):
        self.item = item
        self.ident = item.ident
        self.dest = dest

    def _run_impl(self, a, b):

        if self.dest.storage.read_only:
            href = etag = None
        else:
            sync_logger.info(u'Copying (uploading) item {} to {}'
                             .format(self.ident, self.dest.storage))
            href, etag = self.dest.storage.upload(self.item)

        assert self.ident not in self.dest.new_status
        self.dest.new_status[self.ident] = {
            'href': href,
            'hash': self.item.hash,
            'etag': etag
        }


class Update(Action):
    def __init__(self, item, dest):
        self.item = item
        self.ident = item.ident
        self.dest = dest

    def _run_impl(self, a, b):

        if self.dest.storage.read_only:
            href = etag = None
        else:
            sync_logger.info(u'Copying (updating) item {} to {}'
                             .format(self.ident, self.dest.storage))
            meta = self.dest.new_status[self.ident]
            href = meta['href']
            etag = self.dest.storage.update(href, self.item, meta['etag'])
            assert isinstance(etag, (bytes, str))

        self.dest.new_status[self.ident] = {
            'href': href,
            'hash': self.item.hash,
            'etag': etag
        }


class Delete(Action):
    def __init__(self, ident, dest):
        self.ident = ident
        self.dest = dest

    def _run_impl(self, a, b):
        meta = self.dest.new_status[self.ident]
        if not self.dest.storage.read_only:
            sync_logger.info(u'Deleting item {} from {}'
                             .format(self.ident, self.dest.storage))
            self.dest.storage.delete(meta['href'], meta['etag'])
        del self.dest.new_status[self.ident]


class ResolveConflict(Action):
    def __init__(self, ident):
        self.ident = ident

    def run(self, a, b, conflict_resolution, partial_sync):
        with self.auto_rollback(a, b):
            sync_logger.info(u'Doing conflict resolution for item {}...'
                             .format(self.ident))
            meta_a = a.new_status[self.ident]
            meta_b = b.new_status[self.ident]

            if meta_a['item'].hash == meta_b['item'].hash:
                sync_logger.info(u'...same content on both sides.')
            elif conflict_resolution is None:
                raise SyncConflict(ident=self.ident, href_a=meta_a['href'],
                                   href_b=meta_b['href'])
            elif callable(conflict_resolution):
                new_item = conflict_resolution(meta_a['item'], meta_b['item'])
                if new_item.hash != meta_a['item'].hash:
                    Update(new_item, a).run(a, b, conflict_resolution,
                                            partial_sync)
                if new_item.hash != meta_b['item'].hash:
                    Update(new_item, b).run(a, b, conflict_resolution,
                                            partial_sync)
            else:
                raise exceptions.UserError(
                    'Invalid conflict resolution mode: {!r}'
                    .format(conflict_resolution))


def _get_actions(a_info, b_info):
    for ident in uniq(itertools.chain(a_info.new_status, b_info.new_status,
                                      a_info.status)):
        a = a_info.new_status.get(ident, None)  # item exists in a
        b = b_info.new_status.get(ident, None)  # item exists in b

        if a and b:
            a_changed = a_info.is_changed(ident)
            b_changed = b_info.is_changed(ident)
            if a_changed and b_changed:
                # item was modified on both sides
                # OR: missing status
                yield ResolveConflict(ident)
            elif a_changed and not b_changed:
                # item was only modified in a
                yield Update(a['item'], b_info)
            elif not a_changed and b_changed:
                # item was only modified in b
                yield Update(b['item'], a_info)
        elif a and not b:
            if a_info.is_changed(ident):
                # was deleted from b but modified on a
                # OR: new item was created in a
                yield Upload(a['item'], b_info)
            else:
                # was deleted from b and not modified on a
                yield Delete(ident, a_info)
        elif not a and b:
            if b_info.is_changed(ident):
                # was deleted from a but modified on b
                # OR: new item was created in b
                yield Upload(b['item'], a_info)
            else:
                # was deleted from a and not changed on b
                yield Delete(ident, b_info)
