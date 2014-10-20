# -*- coding: utf-8 -*-
'''
    vdirsyncer.sync
    ~~~~~~~~~~~~~~~

    The function in `vdirsyncer.sync` can be called on two instances of
    `Storage` to synchronize them. Due to the abstract API storage classes are
    implementing, the two given instances don't have to be of the same exact
    type. This allows us not only to synchronize a local vdir with a CalDAV
    server, but also synchronize two CalDAV servers or two local vdirs.

    The algorithm is based on the blogpost "How OfflineIMAP works" by Edward Z.
    Yang. http://blog.ezyang.com/2012/08/how-offlineimap-works/

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''
import itertools

from . import exceptions, log
from .utils.compat import iteritems, text_type
sync_logger = log.get(__name__)


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


def _prepare_idents(storage, other_storage, href_to_status):
    hrefs = {}
    download = []
    for href, etag in storage.list():
        props = hrefs[href] = {'etag': etag, 'href': href}
        if href in href_to_status:
            ident, old_etag = href_to_status[href]
            props['ident'] = ident
            if etag != old_etag and not other_storage.read_only:
                download.append(href)
        else:
            download.append(href)

    _prefetch(storage, hrefs, download)
    return dict((x['ident'], x) for href, x in iteritems(hrefs))


def _prefetch(storage, rv, hrefs):
    if rv is None:
        rv = {}
    if not hrefs:
        return rv

    for href, item, etag in storage.get_multi(hrefs):
        props = rv[href]
        props['item'] = item
        props['ident'] = item.ident
        if props['etag'] != etag:
            raise SyncError('Etag changed during sync.')

    return rv


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

    a_href_to_status = dict(
        (href_a, (ident, etag_a))
        for ident, (href_a, etag_a, href_b, etag_b) in iteritems(status)
    )
    b_href_to_status = dict(
        (href_b, (ident, etag_b))
        for ident, (href_a, etag_a, href_b, etag_b) in iteritems(status)
    )
    # ident => {'etag': etag, 'item': optional item, 'href': href}
    a_idents = _prepare_idents(storage_a, storage_b, a_href_to_status)
    b_idents = _prepare_idents(storage_b, storage_a, b_href_to_status)

    if bool(a_idents) != bool(b_idents) and status and not force_delete:
        raise StorageEmpty(
            empty_storage=(storage_b if a_idents else storage_a))

    del a_href_to_status, b_href_to_status

    storages = {
        'a': (storage_a, a_idents),
        'b': (storage_b, b_idents)
    }

    actions = list(_get_actions(storages, status))

    for action in actions:
        action(storages, status, conflict_resolution)


def _action_upload(ident, dest):
    source = 'a' if dest == 'b' else 'b'

    def inner(storages, status, conflict_resolution):
        source_storage, source_idents = storages[source]
        dest_storage, dest_idents = storages[dest]
        sync_logger.info('Copying (uploading) item {} to {}'
                         .format(ident, dest_storage))

        source_meta = source_idents[ident]
        source_href = source_meta['href']
        source_etag = source_meta['etag']
        source_status = (source_href, source_etag)

        dest_status = (None, None)

        if dest_storage.read_only:
            sync_logger.warning('{dest} is read-only. Skipping update...'
                                .format(dest=dest_storage))
        else:
            item = source_meta['item']
            dest_href, dest_etag = dest_storage.upload(item)
            dest_status = (dest_href, dest_etag)

        status[ident] = source_status + dest_status if source == 'a' else \
            dest_status + source_status

    return inner


def _action_update(ident, dest):
    source = 'a' if dest == 'b' else 'b'

    def inner(storages, status, conflict_resolution):
        source_storage, source_idents = storages[source]
        dest_storage, dest_idents = storages[dest]
        sync_logger.info('Copying (updating) item {} to {}'
                         .format(ident, dest_storage))

        source_meta = source_idents[ident]
        source_href = source_meta['href']
        source_etag = source_meta['etag']
        source_status = (source_href, source_etag)

        dest_meta = dest_idents[ident]
        dest_href = dest_meta['href']
        dest_etag = dest_meta['etag']
        dest_status = (dest_href, dest_etag)

        if dest_storage.read_only:
            sync_logger.info('{dest} is read-only. Skipping update...'
                             .format(dest=dest_storage))
        else:
            item = source_meta['item']
            dest_etag = dest_storage.update(dest_href, item, dest_etag)
            assert isinstance(dest_etag, (bytes, text_type))

            dest_status = (dest_href, dest_etag)

        status[ident] = source_status + dest_status if source == 'a' else \
            dest_status + source_status

    return inner


def _action_delete(ident, dest):
    def inner(storages, status, conflict_resolution):
        if dest is not None:
            dest_storage, dest_idents = storages[dest]
            sync_logger.info('Deleting item {} from {}'
                             .format(ident, dest_storage))
            if dest_storage.read_only:
                sync_logger.warning('{dest} is read-only, skipping deletion...'
                                    .format(dest=dest_storage))
            else:
                dest_meta = dest_idents[ident]
                dest_etag = dest_meta['etag']
                dest_href = dest_meta['href']
                dest_storage.delete(dest_href, dest_etag)
        else:
            sync_logger.info('Deleting status info for nonexisting item {}'
                             .format(ident))

        del status[ident]

    return inner


def _action_conflict_resolve(ident):
    def inner(storages, status, conflict_resolution):
        sync_logger.info('Doing conflict resolution for item {}...'
                         .format(ident))
        a_storage, a_idents = storages['a']
        b_storage, b_idents = storages['b']
        meta_a = a_idents[ident]
        meta_b = b_idents[ident]
        href_a = meta_a['href']
        href_b = meta_b['href']
        if meta_a['item'].raw == meta_b['item'].raw:
            sync_logger.info('...same content on both sides.')
            status[ident] = href_a, meta_a['etag'], href_b, meta_b['etag']
        elif conflict_resolution is None:
            raise SyncConflict(ident=ident, href_a=href_a, href_b=href_b)
        elif conflict_resolution == 'a wins':
            sync_logger.info('...{} wins.'.format(a_storage))
            _action_update(ident, 'b')(storages, status, conflict_resolution)
        elif conflict_resolution == 'b wins':
            sync_logger.info('...{} wins.'.format(b_storage))
            _action_update(ident, 'a')(storages, status, conflict_resolution)
        else:
            raise ValueError('Invalid conflict resolution mode: {}'
                             .format(conflict_resolution))

    return inner


def _get_actions(storages, status):
    storage_a, a_idents = storages['a']
    storage_b, b_idents = storages['b']

    handled = set()
    for ident in itertools.chain(a_idents, b_idents, status):
        if ident in handled:
            continue
        handled.add(ident)

        a = a_idents.get(ident, None)
        b = b_idents.get(ident, None)
        assert not a or a['etag'] is not None
        assert not b or b['etag'] is not None

        try:
            _, status_etag_a, _, status_etag_b = status[ident]
        except KeyError:
            status_etag_a = status_etag_b = None

        if a and b:
            if a['etag'] != status_etag_a and b['etag'] != status_etag_b:
                # item was modified on both sides
                # OR: missing status
                yield _action_conflict_resolve(ident)
            elif a['etag'] != status_etag_a:
                # item was only modified in a
                yield _action_update(ident, 'b')
            elif b['etag'] != status_etag_b:
                # item was only modified in b
                yield _action_update(ident, 'a')
        elif a and not b:
            if a['etag'] != status_etag_a:
                # was deleted from b but modified on a
                # OR: new item was created in a
                yield _action_upload(ident, 'b')
            else:
                # was deleted from b and not modified on a
                yield _action_delete(ident, 'a')
        elif not a and b:
            if b['etag'] != status_etag_b:
                # was deleted from a but modified on b
                # OR: new item was created in b
                yield _action_upload(ident, 'a')
            else:
                # was deleted from a and not changed on b
                yield _action_delete(ident, 'b')
        elif not a and not b:
            # was deleted from a and b, clean up status
            yield _action_delete(ident, None)
