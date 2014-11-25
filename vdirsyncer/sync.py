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
from collections import defaultdict

from . import exceptions, log
from .utils.compat import iteritems
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

    _dispatch_actions(_get_actions(storages, status), storages, status,
                      conflict_resolution)


def _dispatch_actions(actions, storages, status, conflict_resolution):
    action_lists = defaultdict(list)
    for action_type, ident, dest in actions:
        action_lists[(action_type, dest)].append(ident)

    for source, dest in ('ab', 'ba'):
        idents = action_lists.pop(('upload', dest), ())
        if idents:
            _upload(idents, dest, storages, status, conflict_resolution)

        idents = action_lists.pop(('update', dest), ())
        if idents:
            _update(idents, dest, storages, status, conflict_resolution)

        idents = action_lists.pop(('delete', dest), ())
        if idents:
            _delete(idents, dest, storages, status, conflict_resolution)

    idents = action_lists.pop(('delete', None), ())
    if idents:
        _delete(idents, None, storages, status, conflict_resolution)

    for ident in action_lists.pop(('conflict', None), ()):
        _conflict_resolve(ident, storages, status, conflict_resolution)

    assert not action_lists


def _upload(idents, dest, storages, status, conflict_resolution):
    source = 'a' if dest == 'b' else 'b'
    source_storage, source_idents = storages[source]
    dest_storage, dest_idents = storages[dest]

    items = []
    source_statuses = []
    dest_statuses = []

    sync_logger.info('Copying (uploading) items to {}:'.format(dest_storage))

    for ident in idents:
        sync_logger.info('    {}'.format(ident))
        source_meta = source_idents[ident]
        source_statuses.append((source_meta['href'], source_meta['etag']))
        items.append(source_meta['item'])

    if dest_storage.read_only:
        sync_logger.warning('{dest} is read-only. Skipping update...'
                            .format(dest=dest_storage))
        for ident in idents:
            dest_statuses.append((None, None))
    else:
        for ident, (dest_href, dest_etag) in zip(
            idents,
            dest_storage.upload_multi(items)
        ):
            dest_statuses.append((dest_href, dest_etag))

    for ident, source_status, dest_status in zip(
        idents, source_statuses, dest_statuses
    ):
        status[ident] = source_status + dest_status if source == 'a' else \
            dest_status + source_status


def _update(idents, dest, storages, status, conflict_resolution):
    source = 'a' if dest == 'b' else 'b'
    source_storage, source_idents = storages[source]
    dest_storage, dest_idents = storages[dest]

    items = []
    hrefs = []
    source_statuses = []
    dest_statuses = []

    sync_logger.info('Copying (updating) items to {}:'.format(dest_storage))

    for ident in idents:
        sync_logger.info('    {}'.format(ident))
        source_meta = source_idents[ident]
        href = source_meta['href']
        item = source_meta['item']
        etag = source_meta['etag']
        dest_etag = dest_idents[ident]['etag']
        source_statuses.append((href, etag))
        hrefs.append(href)
        items.append((href, item, dest_etag))

    if dest_storage.read_only:
        sync_logger.warning('{dest} is read-only. Skipping update...'
                            .format(dest=dest_storage))
        for ident in idents:
            dest_statuses.append((None, None))
    else:
        for ident, href, new_etag in zip(
            idents, hrefs,
            dest_storage.update_multi(items)
        ):
            dest_statuses.append((href, new_etag))

    for ident, source_status, dest_status in zip(
        idents, source_statuses, dest_statuses
    ):
        status[ident] = source_status + dest_status if source == 'a' else \
            dest_status + source_status


def _delete(idents, dest, storages, status, conflict_resolution):
    to_delete = []

    if dest is None:
        sync_logger.info('Deleting status info for nonexistent items:')

        for ident in idents:
            sync_logger.info('    {}'.format(ident))
    else:
        dest_storage, dest_idents = storages[dest]
        sync_logger.info('Deleting items from {}:'.format(dest_storage))

        for ident in idents:
            sync_logger.info('    {}'.format(ident))
            dest_meta = dest_idents[ident]
            dest_etag = dest_meta['etag']
            dest_href = dest_meta['href']
            to_delete.append((dest_href, dest_etag))

        if dest_storage.read_only:
            sync_logger.warning('{dest} is read-only, skipping deletion...'
                                .format(dest=dest_storage))
        else:
            dest_storage.delete_multi(to_delete)

    for ident in idents:
        del status[ident]


def _conflict_resolve(ident, storages, status, conflict_resolution):
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
        _update([ident], 'b', storages, status, conflict_resolution)
    elif conflict_resolution == 'b wins':
        sync_logger.info('...{} wins.'.format(b_storage))
        _update([ident], 'a', storages, status, conflict_resolution)
    else:
        raise ValueError('Invalid conflict resolution mode: {}'
                         .format(conflict_resolution))


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
                yield 'conflict', ident, None
            elif a['etag'] != status_etag_a:
                # item was only modified in a
                yield 'update', ident, 'b'
            elif b['etag'] != status_etag_b:
                # item was only modified in b
                yield 'update', ident, 'a'
        elif a and not b:
            if a['etag'] != status_etag_a:
                # was deleted from b but modified on a
                # OR: new item was created in a
                yield 'upload', ident, 'b'
            else:
                # was deleted from b and not modified on a
                yield 'delete', ident, 'a'
        elif not a and b:
            if b['etag'] != status_etag_b:
                # was deleted from a but modified on b
                # OR: new item was created in b
                yield 'upload', ident, 'a'
            else:
                # was deleted from a and not changed on b
                yield 'delete', ident, 'b'
        elif not a and not b:
            # was deleted from a and b, clean up status
            yield 'delete', ident, None
