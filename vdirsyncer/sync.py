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

import vdirsyncer.exceptions as exceptions
import vdirsyncer.log
from .utils import iteritems, itervalues
sync_logger = vdirsyncer.log.get(__name__)


def prepare_list(storage, href_to_status):
    download = []
    for href, etag in storage.list():
        props = {'etag': etag}
        if href in href_to_status:
            uid, old_etag = href_to_status[href]
            props['uid'] = uid
            if etag != old_etag:
                download.append(href)
        else:
            download.append(href)
        yield href, props

    if download:
        for href, item, etag in storage.get_multi(download):
            props = {'item': item, 'uid': item.uid, 'etag': etag}
            yield href, props


def sync(storage_a, storage_b, status, conflict_resolution=None):
    '''Syncronizes two storages.

    :param storage_a: The first storage
    :type storage_a: :class:`vdirsyncer.storage.base.Storage`
    :param storage_b: The second storage
    :type storage_b: :class:`vdirsyncer.storage.base.Storage`
    :param status: {uid: (href_a, etag_a, href_b, etag_b)}
        metadata about the two storages for detection of changes. Will be
        modified by the function and should be passed to it at the next sync.
        If this is the first sync, an empty dictionary should be provided.
    :param conflict_resolution: Either 'a wins' or 'b wins'. If none is
        provided, the sync function will raise
        :py:exc:`vdirsyncer.exceptions.SyncConflict`.
    '''
    a_href_to_status = dict(
        (href_a, (uid, etag_a))
        for uid, (href_a, etag_a, href_b, etag_b) in iteritems(status)
    )
    b_href_to_status = dict(
        (href_b, (uid, etag_b))
        for uid, (href_a, etag_a, href_b, etag_b) in iteritems(status)
    )
    # href => {'etag': etag, 'item': optional item, 'uid': uid}
    list_a = dict(prepare_list(storage_a, a_href_to_status))
    list_b = dict(prepare_list(storage_b, b_href_to_status))

    a_uid_to_href = dict((x['uid'], href) for href, x in iteritems(list_a))
    b_uid_to_href = dict((x['uid'], href) for href, x in iteritems(list_b))
    del a_href_to_status, b_href_to_status

    storages = {
        'a': (storage_a, list_a, a_uid_to_href),
        'b': (storage_b, list_b, b_uid_to_href)
    }

    actions = list(get_actions(storages, status))

    for action in actions:
        action(storages, status, conflict_resolution)


def action_upload(uid, source, dest):
    def inner(storages, status, conflict_resolution):
        source_storage, source_list, source_uid_to_href = storages[source]
        dest_storage, dest_list, dest_uid_to_href = storages[dest]
        sync_logger.info('Copying (uploading) item {} to {}'
                         .format(uid, dest_storage))

        source_href = source_uid_to_href[uid]
        source_etag = source_list[source_href]['etag']

        item = source_list[source_href]['item']
        dest_href, dest_etag = dest_storage.upload(item)

        source_status = (source_href, source_etag)
        dest_status = (dest_href, dest_etag)
        status[uid] = source_status + dest_status if source == 'a' else \
            dest_status + source_status

    return inner


def action_update(uid, source, dest):
    def inner(storages, status, conflict_resolution):
        source_storage, source_list, source_uid_to_href = storages[source]
        dest_storage, dest_list, dest_uid_to_href = storages[dest]
        sync_logger.info('Copying (updating) item {} to {}'
                         .format(uid, dest_storage))
        source_href = source_uid_to_href[uid]
        source_etag = source_list[source_href]['etag']

        dest_href = dest_uid_to_href[uid]
        old_etag = dest_list[dest_href]['etag']
        item = source_list[source_href]['item']
        dest_etag = dest_storage.update(dest_href, item, old_etag)

        source_status = (source_href, source_etag)
        dest_status = (dest_href, dest_etag)
        status[uid] = source_status + dest_status if source == 'a' else \
            dest_status + source_status

    return inner


def action_delete(uid, dest):
    def inner(storages, status, conflict_resolution):
        if dest is not None:
            dest_storage, dest_list, dest_uid_to_href = storages[dest]
            sync_logger.info('Deleting item {} from {}'
                             .format(uid, dest_storage))
            dest_href = dest_uid_to_href[uid]
            dest_etag = dest_list[dest_href]['etag']
            dest_storage.delete(dest_href, dest_etag)
        else:
            sync_logger.info('Deleting status info for nonexisting item {}'
                             .format(uid))
        del status[uid]

    return inner


def action_conflict_resolve(uid):
    def inner(storages, status, conflict_resolution):
        sync_logger.info('Doing conflict resolution for item {}...'
                         .format(uid))
        a_storage, list_a, a_uid_to_href = storages['a']
        b_storage, list_b, b_uid_to_href = storages['b']
        a_href = a_uid_to_href[uid]
        b_href = b_uid_to_href[uid]
        a_meta = list_a[a_href]
        b_meta = list_b[b_href]
        if a_meta['item'].raw == b_meta['item'].raw:
            sync_logger.info('...same content on both sides.')
            status[uid] = a_href, a_meta['etag'], b_href, b_meta['etag']
        elif conflict_resolution is None:
            raise exceptions.SyncConflict()
        elif conflict_resolution == 'a wins':
            sync_logger.info('...{} wins.'.format(a_storage))
            action_update(uid, 'a', 'b')(storages, status, conflict_resolution)
        elif conflict_resolution == 'b wins':
            sync_logger.info('...{} wins.'.format(b_storage))
            action_update(uid, 'b', 'a')(storages, status, conflict_resolution)
        else:
            raise ValueError('Invalid conflict resolution mode: {}'
                             .format(conflict_resolution))

    return inner


def get_actions(storages, status):
    storage_a, list_a, a_uid_to_href = storages['a']
    storage_b, list_b, b_uid_to_href = storages['b']

    uids_a = (x['uid'] for x in itervalues(list_a))
    uids_b = (x['uid'] for x in itervalues(list_b))
    handled = set()
    for uid in itertools.chain(uids_a, uids_b, status):
        if uid in handled:
            continue
        handled.add(uid)

        href_a = a_uid_to_href.get(uid, None)
        href_b = b_uid_to_href.get(uid, None)
        a = list_a.get(href_a, None)
        b = list_b.get(href_b, None)
        if uid not in status:
            if a and b:  # missing status
                yield action_conflict_resolve(uid)
            elif a and not b:  # new item was created in a
                yield action_upload(uid, 'a', 'b')
            elif not a and b:  # new item was created in b
                yield action_upload(uid, 'b', 'a')
        else:
            _, status_etag_a, _, status_etag_b = status[uid]
            if a and b:
                if a['etag'] != status_etag_a and b['etag'] != status_etag_b:
                    yield action_conflict_resolve(uid)
                elif a['etag'] != status_etag_a:  # item was updated in a
                    yield action_update(uid, 'a', 'b')
                elif b['etag'] != status_etag_b:  # item was updated in b
                    yield action_update(uid, 'b', 'a')
            elif a and not b:  # was deleted from b
                yield action_delete(uid, 'a')
            elif not a and b:  # was deleted from a
                yield action_delete(uid, 'b')
            elif not a and not b:  # was deleted from a and b
                yield action_delete(uid, None)
