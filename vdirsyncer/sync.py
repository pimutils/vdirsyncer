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
from .utils.compat import iteritems, text_type

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
        val = set(val)
        assert len(val) > 1
        self._hrefs = val


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


class StorageSyncer(object):
    '''A wrapper class that holds prefetched items, the status and other
    things.'''
    def __init__(self, storage, status):
        '''
        :param status: {ident: {'href': href, 'etag': etag}}
        '''
        self.storage = storage
        self.status = status
        self.idents = None

    def prepare_idents(self):
        href_to_status = dict((meta['href'], (ident, meta))
                              for ident, meta
                              in iteritems(self.status))

        prefetch = {}
        self.idents = {}

        def _store_props(ident, props):
            if self.idents.setdefault(ident, props) is not props:
                raise IdentConflict(storage=self.storage,
                                    hrefs=[self.idents[ident]['href'],
                                           href])

            if ident in self.status:
                # Necessary if item's href changes.
                # Otherwise it's a no-op, like `a = a`.
                self.status[ident]['href'] = props['href']

        for href, etag in self.storage.list():
            props = {'href': href, 'etag': etag}
            ident, old_meta = href_to_status.get(href, (None, None))
            assert etag is not None
            if old_meta is None or etag != old_meta['etag']:
                # Either the item is completely new, or updated
                # In both cases we should prefetch
                prefetch[href] = props
            else:
                _store_props(ident, props)

        # Prefetch items
        for href, item, etag in (self.storage.get_multi(prefetch)
                                 if prefetch else ()):
            props = prefetch[href]

            assert props['href'] == href
            if props['etag'] != etag:
                sync_logger.warning(
                    'Etag of {!r} changed during sync from {!r} to {!r}'
                    .format(href, props['etag'], etag)
                )
            props['etag'] = etag
            props['item'] = item
            props['ident'] = ident = item.ident
            _store_props(ident, props)

    def is_changed(self, ident):
        status = self.status.get(ident, None)
        meta = self.idents[ident]

        if status is None:  # new item
            return True

        if meta['etag'] != status['etag']:  # etag changed
            old_hash = status.get('hash')
            if old_hash is None or meta['item'].hash != old_hash:
                # item actually changed
                return True
            else:
                # only etag changed
                status['etag'] = meta['etag']
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


def _compress_meta(meta):
    '''Make in-memory metadata suitable for disk storage by removing fetched
    item content'''
    return {
        'href': meta['href'],
        'etag': meta['etag'],
        'hash': meta['item'].hash
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
    :param conflict_resolution: Either 'a wins' or 'b wins'. If none is
        provided, the sync function will raise
        :py:exc:`SyncConflict`.
    :param force_delete: When one storage got completely emptied between two
        syncs, :py:exc:`StorageEmpty` is raised for
        safety. Setting this parameter to ``True`` disables this safety
        measure.
    '''
    if storage_a.read_only and storage_b.read_only:
        raise BothReadOnly()

    _status_migrate(status)

    a_info = storage_a.syncer_class(storage_a, dict(
        (ident, meta_a)
        for ident, (meta_a, meta_b) in iteritems(status)
    ))
    b_info = storage_b.syncer_class(storage_b, dict(
        (ident, meta_b)
        for ident, (meta_a, meta_b) in iteritems(status)
    ))

    a_info.prepare_idents()
    b_info.prepare_idents()

    if bool(a_info.idents) != bool(b_info.idents) \
       and status and not force_delete:
        raise StorageEmpty(
            empty_storage=(storage_b if a_info.idents else storage_a))

    actions = list(_get_actions(a_info, b_info))

    with storage_a.at_once():
        with storage_b.at_once():
            for action in actions:
                action(a_info, b_info, conflict_resolution)

    status.clear()
    for ident in uniq(itertools.chain(a_info.status, b_info.status)):
        status[ident] = a_info.status[ident], b_info.status[ident]


def _action_upload(ident, source, dest):

    def inner(a, b, conflict_resolution):
        sync_logger.info(u'Copying (uploading) item {} to {}'
                         .format(ident, dest.storage))
        source_meta = source.idents[ident]

        if dest.storage.read_only:
            sync_logger.warning('{dest} is read-only. Skipping update...'
                                .format(dest=dest.storage))
            dest_href = dest_etag = None
        else:
            item = source_meta['item']
            dest_href, dest_etag = dest.storage.upload(item)

        source.status[ident] = _compress_meta(source_meta)
        dest.status[ident] = {
            'href': dest_href,
            'hash': source_meta['item'].hash,
            'etag': dest_etag
        }

    return inner


def _action_update(ident, source, dest):

    def inner(a, b, conflict_resolution):
        sync_logger.info(u'Copying (updating) item {} to {}'
                         .format(ident, dest.storage))
        source_meta = source.idents[ident]

        if dest.storage.read_only:
            sync_logger.warning(u'{dest} is read-only. Skipping update...'
                                .format(dest=dest.storage))
            dest_href = dest_etag = None
        else:
            dest_meta = dest.idents[ident]
            dest_href = dest_meta['href']
            dest_etag = dest.storage.update(dest_href, source_meta['item'],
                                            dest_meta['etag'])
            assert isinstance(dest_etag, (bytes, text_type))

        source.status[ident] = _compress_meta(source_meta)
        dest.status[ident] = {
            'href': dest_href,
            'hash': source_meta['item'].hash,
            'etag': dest_etag
        }

    return inner


def _action_delete(ident, info):
    storage = info.storage
    idents = info.idents

    def inner(a, b, conflict_resolution):
        sync_logger.info(u'Deleting item {} from {}'.format(ident, storage))
        if storage.read_only:
            sync_logger.warning('{} is read-only, skipping deletion...'
                                .format(storage))
        else:
            meta = idents[ident]
            etag = meta['etag']
            href = meta['href']
            storage.delete(href, etag)

        del a.status[ident]
        del b.status[ident]

    return inner


def _action_delete_status(ident):
    def inner(a, b, conflict_resolution):
        sync_logger.info(u'Deleting status info for nonexisting item {}'
                         .format(ident))
        del a.status[ident]
        del b.status[ident]

    return inner


def _action_conflict_resolve(ident):
    def inner(a, b, conflict_resolution):
        sync_logger.info(u'Doing conflict resolution for item {}...'
                         .format(ident))
        meta_a = a.idents[ident]
        meta_b = b.idents[ident]

        if meta_a['item'].hash == meta_b['item'].hash:
            sync_logger.info(u'...same content on both sides.')
            a.status[ident] = _compress_meta(meta_a)
            b.status[ident] = _compress_meta(meta_b)
        elif conflict_resolution is None:
            raise SyncConflict(ident=ident, href_a=meta_a['href'],
                               href_b=meta_b['href'])
        elif conflict_resolution == 'a wins':
            sync_logger.info(u'...{} wins.'.format(a.storage))
            _action_update(ident, a, b)(a, b, conflict_resolution)
        elif conflict_resolution == 'b wins':
            sync_logger.info(u'...{} wins.'.format(b.storage))
            _action_update(ident, b, a)(a, b, conflict_resolution)
        else:
            raise exceptions.UserError('Invalid conflict resolution mode: {}'
                                       .format(conflict_resolution))

    return inner


def _get_actions(a_info, b_info):
    for ident in uniq(itertools.chain(a_info.idents, b_info.idents,
                                      a_info.status)):
        a = ident in a_info.idents  # item exists in a
        b = ident in b_info.idents  # item exists in b

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
        elif not a and not b:
            # was deleted from a and b, clean up status
            yield _action_delete_status(ident)
