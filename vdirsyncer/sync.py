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

    def upload_full(self, item):
        if self.storage.read_only:
            sync_logger.warning('{} is read-only. Skipping update...'
                                .format(self.storage))
            href = etag = None
        else:
            href, etag = self.storage.upload(item)

        assert item.ident not in self.new_status
        self.new_status[item.ident] = {
            'href': href,
            'hash': item.hash,
            'etag': etag
        }

    def update_full(self, item):
        '''Similar to Storage.update, but automatically takes care of ETags and
        updating the status.'''

        if self.storage.read_only:
            sync_logger.warning('{} is read-only. Skipping update...'
                                .format(self.storage))
            href = etag = None
        else:
            meta = self.new_status[item.ident]
            href = meta['href']
            etag = self.storage.update(href, item, meta['etag'])
            assert isinstance(etag, (bytes, str))

        self.new_status[item.ident] = {
            'href': href,
            'hash': item.hash,
            'etag': etag
        }

    def delete_full(self, ident):
        meta = self.new_status.pop(ident)
        if self.storage.read_only:
            sync_logger.warning('{} is read-only, skipping deletion...'
                                .format(self.storage))
        else:
            self.storage.delete(meta['href'], meta['etag'])


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
         force_delete=False):
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
    '''
    if storage_a.read_only and storage_b.read_only:
        raise BothReadOnly()

    if conflict_resolution == 'a wins':
        conflict_resolution = lambda a, b: a
    elif conflict_resolution == 'b wins':
        conflict_resolution = lambda a, b: b

    _status_migrate(status)

    a_info = _StorageInfo(storage_a, dict(
        (ident, meta_a)
        for ident, (meta_a, meta_b) in status.items()
    ))
    b_info = _StorageInfo(storage_b, dict(
        (ident, meta_b)
        for ident, (meta_a, meta_b) in status.items()
    ))

    a_info.prepare_new_status()
    b_info.prepare_new_status()

    if status and not force_delete:
        if a_info.new_status and not b_info.new_status:
            raise StorageEmpty(empty_storage=storage_b)
        elif b_info.new_status and not a_info.new_status:
            raise StorageEmpty(empty_storage=storage_a)

    actions = list(_get_actions(a_info, b_info))

    with storage_a.at_once():
        with storage_b.at_once():
            for action in actions:
                action(a_info, b_info, conflict_resolution)

    status.clear()
    for ident in uniq(itertools.chain(a_info.new_status, b_info.new_status)):
        status[ident] = (
            _compress_meta(a_info.new_status[ident]),
            _compress_meta(b_info.new_status[ident])
        )


def _action_upload(ident, source, dest):

    def inner(a, b, conflict_resolution):
        sync_logger.info(u'Copying (uploading) item {} to {}'
                         .format(ident, dest.storage))
        item = source.new_status[ident]['item']
        dest.upload_full(item)

    return inner


def _action_update(ident, source, dest):
    def inner(a, b, conflict_resolution):
        sync_logger.info(u'Copying (updating) item {} to {}'
                         .format(ident, dest.storage))
        source_meta = source.new_status[ident]
        dest.update_full(source_meta['item'])

    return inner


def _action_delete(ident, info):
    def inner(a, b, conflict_resolution):
        sync_logger.info(u'Deleting item {} from {}'
                         .format(ident, info.storage))
        info.delete_full(ident)

    return inner


def _action_conflict_resolve(ident):
    def inner(a, b, conflict_resolution):
        sync_logger.info(u'Doing conflict resolution for item {}...'
                         .format(ident))
        meta_a = a.new_status[ident]
        meta_b = b.new_status[ident]

        if meta_a['item'].hash == meta_b['item'].hash:
            sync_logger.info(u'...same content on both sides.')
        elif conflict_resolution is None:
            raise SyncConflict(ident=ident, href_a=meta_a['href'],
                               href_b=meta_b['href'])
        elif callable(conflict_resolution):
            new_item = conflict_resolution(meta_a['item'], meta_b['item'])
            if new_item.hash != meta_a['item'].hash:
                a.update_full(new_item)
            if new_item.hash != meta_b['item'].hash:
                b.update_full(new_item)
        else:
            raise exceptions.UserError('Invalid conflict resolution mode: {!r}'
                                       .format(conflict_resolution))

    return inner


def _get_actions(a_info, b_info):
    for ident in uniq(itertools.chain(a_info.new_status, b_info.new_status,
                                      a_info.status)):
        a = ident in a_info.new_status  # item exists in a
        b = ident in b_info.new_status  # item exists in b

        if a and b:
            a_changed = a_info.is_changed(ident)
            b_changed = b_info.is_changed(ident)
            if a_changed and b_changed:
                # item was modified on both sides
                # OR: missing status
                yield _action_conflict_resolve(ident)
            elif a_changed and not b_changed:
                # item was only modified in a
                yield _action_update(ident, a_info, b_info)
            elif not a_changed and b_changed:
                # item was only modified in b
                yield _action_update(ident, b_info, a_info)
        elif a and not b:
            if a_info.is_changed(ident):
                # was deleted from b but modified on a
                # OR: new item was created in a
                yield _action_upload(ident, a_info, b_info)
            else:
                # was deleted from b and not modified on a
                yield _action_delete(ident, a_info)
        elif not a and b:
            if b_info.is_changed(ident):
                # was deleted from a but modified on b
                # OR: new item was created in b
                yield _action_upload(ident, b_info, a_info)
            else:
                # was deleted from a and not changed on b
                yield _action_delete(ident, b_info)
