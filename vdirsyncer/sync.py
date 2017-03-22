# -*- coding: utf-8 -*-
'''
The function in `vdirsyncer.sync` can be called on two instances of `Storage`
to synchronize them. Due to the abstract API storage classes are implementing,
the two given instances don't have to be of the same exact type. This allows us
not only to synchronize a local vdir with a CalDAV server, but also synchronize
two CalDAV servers or two local vdirs.

The algorithm is based on the blogpost "How OfflineIMAP works" by Edward Z.
Yang: http://blog.ezyang.com/2012/08/how-offlineimap-works/

Some modifications to it are explained in
https://unterwaditzer.net/2016/sync-algorithm.html
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


class _IdentAlreadyExists(SyncError):
    '''Like IdentConflict, but for internal state. If this bubbles up, we don't
    have a data race, but a bug.'''
    old_href = None
    new_href = None

    def to_ident_conflict(self, storage):
        return IdentConflict(storage=storage,
                             hrefs=[self.old_href, self.new_href])


class _Status(object):
    def __init__(self, ident_to_props):
        self._ident_to_props = ident_to_props
        self._new_ident_to_props = {}

        self._href_to_status_a = dict((meta['href'], (ident, meta))
                                      for ident, (meta, _)
                                      in self._ident_to_props.items())

        self._href_to_status_b = dict((meta['href'], (ident, meta))
                                      for ident, (_, meta)
                                      in self._ident_to_props.items())

    def insert_ident_a(self, ident, props):
        props_a, props_b = self._new_ident_to_props.get(ident, (None, None))
        if props_a is not None:
            raise _IdentAlreadyExists(old_href=props.href,
                                      new_href=props_a['href'])
        self._new_ident_to_props[ident] = props.to_status(), props_b

    def insert_ident_b(self, ident, props):
        props_a, props_b = self._new_ident_to_props.get(ident, (None, None))
        if props_b is not None:
            raise _IdentAlreadyExists(old_href=props.href,
                                      new_href=props_b['href'])
        self._new_ident_to_props[ident] = props_a, props.to_status()

    def update_ident_a(self, ident, props):
        self._new_ident_to_props[ident] = (
            props.to_status(),
            self._new_ident_to_props[ident][1],
        )

    def update_ident_b(self, ident, props):
        self._new_ident_to_props[ident] = (
            self._new_ident_to_props[ident][0],
            props.to_status(),
        )

    def remove_ident(self, ident):
        del self._new_ident_to_props[ident]

    def get_a(self, ident):
        rv = self._ident_to_props[ident][0]
        if rv is None:
            raise KeyError()
        return _ItemMetadata(**rv)

    def get_b(self, ident):
        rv = self._ident_to_props[ident][1]
        if rv is None:
            raise KeyError()
        return _ItemMetadata(**rv)

    def get_new_a(self, ident):
        rv = self._new_ident_to_props[ident][0]
        if rv is None:
            raise KeyError()
        return _ItemMetadata(**rv)

    def get_new_b(self, ident):
        rv = self._new_ident_to_props[ident][1]
        if rv is None:
            raise KeyError()
        return _ItemMetadata(**rv)

    def iter_old(self):
        return iter(self._ident_to_props)

    def iter_new(self):
        return iter(self._new_ident_to_props)

    def rollback(self, ident):
        if ident in self._ident_to_props:
            self._new_ident_to_props[ident] = self._ident_to_props[ident]
        else:
            self._new_ident_to_props.pop(ident, None)

    def get_by_href_a(self, href, default=(None, None)):
        try:
            ident, meta = self._href_to_status_a[href]
        except KeyError:
            return default
        else:
            return ident, _ItemMetadata(**meta)

    def get_by_href_b(self, href, default=(None, None)):
        try:
            ident, meta = self._href_to_status_b[href]
        except KeyError:
            return default
        else:
            return ident, _ItemMetadata(**meta)

    def new_to_old_status(self):
        for meta_a, meta_b in self._new_ident_to_props.values():
            assert meta_a is not None
            assert meta_b is not None

        self._ident_to_props.clear()
        self._ident_to_props.update(self._new_ident_to_props)


class _SubStatus(object):
    def __init__(self, parent, side):
        self.parent = parent
        assert side in 'ab'

        self.remove_ident = parent.remove_ident

        if side == 'a':
            self.insert_ident = parent.insert_ident_a
            self.update_ident = parent.update_ident_a
            self.get = parent.get_a
            self.get_new = parent.get_new_a
            self.get_by_href = parent.get_by_href_a
        else:
            self.insert_ident = parent.insert_ident_b
            self.update_ident = parent.update_ident_b
            self.get = parent.get_b
            self.get_new = parent.get_new_b
            self.get_by_href = parent.get_by_href_b


class _ItemMetadata:
    href = None
    hash = None
    etag = None

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            assert hasattr(self, k)
            setattr(self, k, v)

    def to_status(self):
        return {
            'href': self.href,
            'etag': self.etag,
            'hash': self.hash
        }


class _StorageInfo(object):
    '''A wrapper class that holds prefetched items, the status and other
    things.'''
    def __init__(self, storage, status):
        self.storage = storage
        self.status = status
        self._item_cache = {}

    def prepare_new_status(self):
        storage_nonempty = False
        prefetch = []

        def _store_props(ident, props):
            nonlocal storage_nonempty
            storage_nonempty = True

            try:
                self.status.insert_ident(ident, props)
            except _IdentAlreadyExists as e:
                raise e.to_ident_conflict(self.storage)

        for href, etag in self.storage.list():
            ident, meta = self.status.get_by_href(href)
            if meta is None:
                meta = _ItemMetadata()

            if meta.href != href or meta.etag != etag:
                # Either the item is completely new, or updated
                # In both cases we should prefetch
                prefetch.append(href)
            else:
                meta.href = href
                meta.etag = etag
                _store_props(ident, meta)

        # Prefetch items
        for href, item, etag in (self.storage.get_multi(prefetch)
                                 if prefetch else ()):
            _store_props(item.ident, _ItemMetadata(
                href=href,
                hash=item.hash,
                etag=etag
            ))
            self.set_item_cache(item.ident, item)

        return storage_nonempty

    def is_changed(self, ident):
        try:
            status = self.status.get(ident)
        except KeyError:  # new item
            return True

        meta = self.status.get_new(ident)

        if meta.etag != status.etag:  # etag changed
            old_hash = status.hash
            if old_hash is None or meta.hash != old_hash:
                # item actually changed
                return True
            else:
                # only etag changed
                return False

    def set_item_cache(self, ident, item):
        assert self.status.get_new(ident).hash == item.hash
        self._item_cache[ident] = item

    def get_item_cache(self, ident):
        return self._item_cache[ident]


def _migrate_status(status):
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
        accepted to mean that side's version will always be taken. If none
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

    _migrate_status(status)
    status_nonempty = bool(status)
    status = _Status(status)

    a_info = _StorageInfo(storage_a, _SubStatus(status, 'a'))
    b_info = _StorageInfo(storage_b, _SubStatus(status, 'b'))

    a_nonempty = a_info.prepare_new_status()
    b_nonempty = b_info.prepare_new_status()

    if status_nonempty and not force_delete:
        if a_nonempty and not b_nonempty:
            raise StorageEmpty(empty_storage=storage_b)
        elif not a_nonempty and b_nonempty:
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

    status.new_to_old_status()


class Action:
    def _run_impl(self, a, b):  # pragma: no cover
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
        a.status.parent.rollback(self.ident)


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

        self.dest.status.insert_ident(self.ident, _ItemMetadata(
            href=href,
            hash=self.item.hash,
            etag=etag
        ))


class Update(Action):
    def __init__(self, item, dest):
        self.item = item
        self.ident = item.ident
        self.dest = dest

    def _run_impl(self, a, b):
        if self.dest.storage.read_only:
            meta = _ItemMetadata(hash=self.item.hash)
        else:
            sync_logger.info(u'Copying (updating) item {} to {}'
                             .format(self.ident, self.dest.storage))
            meta = self.dest.status.get_new(self.ident)
            meta.etag = \
                self.dest.storage.update(meta.href, self.item, meta.etag)

        self.dest.status.update_ident(self.ident, meta)


class Delete(Action):
    def __init__(self, ident, dest):
        self.ident = ident
        self.dest = dest

    def _run_impl(self, a, b):
        meta = self.dest.status.get_new(self.ident)
        if not self.dest.storage.read_only:
            sync_logger.info(u'Deleting item {} from {}'
                             .format(self.ident, self.dest.storage))
            self.dest.storage.delete(meta.href, meta.etag)

        self.dest.status.remove_ident(self.ident)


class ResolveConflict(Action):
    def __init__(self, ident):
        self.ident = ident

    def run(self, a, b, conflict_resolution, partial_sync):
        with self.auto_rollback(a, b):
            sync_logger.info(u'Doing conflict resolution for item {}...'
                             .format(self.ident))

            meta_a = a.status.get_new(self.ident)
            meta_b = b.status.get_new(self.ident)

            if meta_a.hash == meta_b.hash:
                sync_logger.info(u'...same content on both sides.')
            elif conflict_resolution is None:
                raise SyncConflict(ident=self.ident, href_a=meta_a.href,
                                   href_b=meta_b.href)
            elif callable(conflict_resolution):
                item_a = a.get_item_cache(self.ident)
                item_b = b.get_item_cache(self.ident)
                new_item = conflict_resolution(item_a, item_b)
                if new_item.hash != meta_a.hash:
                    Update(new_item, a).run(a, b, conflict_resolution,
                                            partial_sync)
                if new_item.hash != meta_b.hash:
                    Update(new_item, b).run(a, b, conflict_resolution,
                                            partial_sync)
            else:
                raise exceptions.UserError(
                    'Invalid conflict resolution mode: {!r}'
                    .format(conflict_resolution))


def _get_actions(a_info, b_info):
    for ident in uniq(itertools.chain(a_info.status.parent.iter_new(),
                                      a_info.status.parent.iter_old())):
        try:
            a = a_info.status.get_new(ident)
        except KeyError:
            a = None

        try:
            b = b_info.status.get_new(ident)
        except KeyError:
            b = None

        if a and b:
            a_changed = a_info.is_changed(ident)
            b_changed = b_info.is_changed(ident)
            if a_changed and b_changed:
                # item was modified on both sides
                # OR: missing status
                yield ResolveConflict(ident)
            elif a_changed and not b_changed:
                # item was only modified in a
                yield Update(a_info.get_item_cache(ident), b_info)
            elif not a_changed and b_changed:
                # item was only modified in b
                yield Update(b_info.get_item_cache(ident), a_info)
        elif a and not b:
            if a_info.is_changed(ident):
                # was deleted from b but modified on a
                # OR: new item was created in a
                yield Upload(a_info.get_item_cache(ident), b_info)
            else:
                # was deleted from b and not modified on a
                yield Delete(ident, a_info)
        elif not a and b:
            if b_info.is_changed(ident):
                # was deleted from a but modified on b
                # OR: new item was created in b
                yield Upload(b_info.get_item_cache(ident), a_info)
            else:
                # was deleted from a and not changed on b
                yield Delete(ident, b_info)
