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

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
import itertools

from . import exceptions, log
from .utils import iteritems
sync_logger = log.get(__name__)


class SyncError(exceptions.Error):
    '''Errors related to synchronization.'''


class SyncConflict(SyncError):
    '''
    Two items changed since the last sync, they now have different contents and
    no conflict resolution method was given.
    '''


class StorageEmpty(SyncError):
    '''
    One storage unexpectedly got completely empty between two synchronizations.
    The first argument is the empty storage.
    '''

    @property
    def empty_storage(self):
        return self.args[0]


def prepare_list(storage, href_to_status):
    rv = {}
    download = []
    for href, etag in storage.list():
        props = rv[href] = {'etag': etag}
        if href in href_to_status:
            ident, old_etag = href_to_status[href]
            props['ident'] = ident
            if etag != old_etag:
                download.append(href)
        else:
            download.append(href)

    if download:
        for href, item, etag in storage.get_multi(download):
            props = rv[href]
            props['item'] = item
            props['ident'] = item.uid or item.hash
            if props['etag'] != etag:
                raise SyncConflict('Etag changed during sync.')

    return rv


def sync(storage_a, storage_b, status, conflict_resolution=None,
         force_delete=False):
    '''Syncronizes two storages.

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
    a_href_to_status = dict(
        (href_a, (ident, etag_a))
        for ident, (href_a, etag_a, href_b, etag_b) in iteritems(status)
    )
    b_href_to_status = dict(
        (href_b, (ident, etag_b))
        for ident, (href_a, etag_a, href_b, etag_b) in iteritems(status)
    )
    # href => {'etag': etag, 'item': optional item, 'ident': ident}
    list_a = prepare_list(storage_a, a_href_to_status)
    list_b = prepare_list(storage_b, b_href_to_status)

    if bool(list_a) != bool(list_b) and status and not force_delete:
        raise StorageEmpty(storage_b if list_a else storage_a)

    a_ident_to_href = dict((x['ident'], href) for href, x in iteritems(list_a))
    b_ident_to_href = dict((x['ident'], href) for href, x in iteritems(list_b))
    del a_href_to_status, b_href_to_status

    storages = {
        'a': (storage_a, list_a, a_ident_to_href),
        'b': (storage_b, list_b, b_ident_to_href)
    }

    actions = list(get_actions(storages, status))

    for action in actions:
        action(storages, status, conflict_resolution)


def action_upload(ident, source, dest):
    def inner(storages, status, conflict_resolution):
        source_storage, source_list, source_ident_to_href = storages[source]
        dest_storage, dest_list, dest_ident_to_href = storages[dest]
        sync_logger.info('Copying (uploading) item {} to {}'
                         .format(ident, dest_storage))

        source_href = source_ident_to_href[ident]
        source_etag = source_list[source_href]['etag']

        item = source_list[source_href]['item']
        dest_href, dest_etag = dest_storage.upload(item)

        source_status = (source_href, source_etag)
        dest_status = (dest_href, dest_etag)
        status[ident] = source_status + dest_status if source == 'a' else \
            dest_status + source_status

    return inner


def action_update(ident, source, dest):
    def inner(storages, status, conflict_resolution):
        source_storage, source_list, source_ident_to_href = storages[source]
        dest_storage, dest_list, dest_ident_to_href = storages[dest]
        sync_logger.info('Copying (updating) item {} to {}'
                         .format(ident, dest_storage))
        source_href = source_ident_to_href[ident]
        source_etag = source_list[source_href]['etag']

        dest_href = dest_ident_to_href[ident]
        old_etag = dest_list[dest_href]['etag']
        item = source_list[source_href]['item']
        dest_etag = dest_storage.update(dest_href, item, old_etag)

        source_status = (source_href, source_etag)
        dest_status = (dest_href, dest_etag)
        status[ident] = source_status + dest_status if source == 'a' else \
            dest_status + source_status

    return inner


def action_delete(ident, dest):
    def inner(storages, status, conflict_resolution):
        if dest is not None:
            dest_storage, dest_list, dest_ident_to_href = storages[dest]
            sync_logger.info('Deleting item {} from {}'
                             .format(ident, dest_storage))
            dest_href = dest_ident_to_href[ident]
            dest_etag = dest_list[dest_href]['etag']
            dest_storage.delete(dest_href, dest_etag)
        else:
            sync_logger.info('Deleting status info for nonexisting item {}'
                             .format(ident))
        del status[ident]

    return inner


def action_conflict_resolve(ident):
    def inner(storages, status, conflict_resolution):
        sync_logger.info('Doing conflict resolution for item {}...'
                         .format(ident))
        a_storage, list_a, a_ident_to_href = storages['a']
        b_storage, list_b, b_ident_to_href = storages['b']
        a_href = a_ident_to_href[ident]
        b_href = b_ident_to_href[ident]
        a_meta = list_a[a_href]
        b_meta = list_b[b_href]
        if a_meta['item'].raw == b_meta['item'].raw:
            sync_logger.info('...same content on both sides.')
            status[ident] = a_href, a_meta['etag'], b_href, b_meta['etag']
        elif conflict_resolution is None:
            raise SyncConflict()
        elif conflict_resolution == 'a wins':
            sync_logger.info('...{} wins.'.format(a_storage))
            action_update(ident, 'a', 'b')(storages, status, conflict_resolution)
        elif conflict_resolution == 'b wins':
            sync_logger.info('...{} wins.'.format(b_storage))
            action_update(ident, 'b', 'a')(storages, status, conflict_resolution)
        else:
            raise ValueError('Invalid conflict resolution mode: {}'
                             .format(conflict_resolution))

    return inner


def get_actions(storages, status):
    storage_a, list_a, a_ident_to_href = storages['a']
    storage_b, list_b, b_ident_to_href = storages['b']

    handled = set()
    for ident in itertools.chain(a_ident_to_href, b_ident_to_href, status):
        if ident in handled:
            continue
        handled.add(ident)

        href_a = a_ident_to_href.get(ident, None)
        href_b = b_ident_to_href.get(ident, None)
        a = list_a.get(href_a, None)
        b = list_b.get(href_b, None)
        if ident not in status:
            if a and b:  # missing status
                yield action_conflict_resolve(ident)
            elif a and not b:  # new item was created in a
                yield action_upload(ident, 'a', 'b')
            elif not a and b:  # new item was created in b
                yield action_upload(ident, 'b', 'a')
        else:
            _, status_etag_a, _, status_etag_b = status[ident]
            if a and b:
                if a['etag'] != status_etag_a and b['etag'] != status_etag_b:
                    yield action_conflict_resolve(ident)
                elif a['etag'] != status_etag_a:  # item was updated in a
                    yield action_update(ident, 'a', 'b')
                elif b['etag'] != status_etag_b:  # item was updated in b
                    yield action_update(ident, 'b', 'a')
            elif a and not b:  # was deleted from b
                yield action_delete(ident, 'a')
            elif not a and b:  # was deleted from a
                yield action_delete(ident, 'b')
            elif not a and not b:  # was deleted from a and b
                yield action_delete(ident, None)
