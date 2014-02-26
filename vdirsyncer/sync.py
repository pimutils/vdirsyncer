# -*- coding: utf-8 -*-
'''
    vdirsyncer.sync
    ~~~~~~~~~~~~~~~

    The function in `vdirsyncer.sync` can be called on two instances of
    `Storage` to syncronize them. Due to the abstract API storage classes are
    implementing, the two given instances don't have to be of the same exact
    type. This allows us not only to syncronize a local vdir with a CalDAV
    server, but also syncronize two CalDAV servers or two local vdirs.

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''


def prepare_list(storage, href_to_uid):
    for href, etag in storage.list():
        props = {'etag': etag}
        if href in href_to_uid:
            props['uid'] = href_to_uid[href]
        else:
            obj, new_etag = storage.get(href)
            assert etag == new_etag
            props['uid'] = obj.uid
            props['obj'] = obj
        yield href, props


def prefetch(storage, item_list, hrefs):
    hrefs_to_prefetch = []
    for href in hrefs:
        if 'obj' not in item_list[href]:
            hrefs_to_prefetch.append(href)
    for href, obj, etag in storage.get_multi(hrefs_to_prefetch):
        assert item_list[href]['etag'] == etag
        item_list[href]['obj'] = obj


def sync(storage_a, storage_b, status):
    '''Syncronizes two storages.

    :param storage_a: The first storage
    :type storage_a: :class:`vdirsyncer.storage.base.Storage`
    :param storage_b: The second storage
    :type storage_b: :class:`vdirsyncer.storage.base.Storage`
    :param status: {uid: (href_a, etag_a, href_b, etag_b)}
        metadata about the two storages for detection of changes. Will be
        modified by the function and should be passed to it at the next sync.
        If this is the first sync, an empty dictionary should be provided.
    '''
    a_href_to_uid = dict((href_a, uid)
                         for uid, (href_a, etag_a, href_b, etag_b) in status.iteritems())
    b_href_to_uid = dict((href_b, uid)
                         for uid, (href_a, etag_a, href_b, etag_b) in status.iteritems())
    # href => {'etag': etag, 'obj': optional object, 'uid': uid}
    list_a = dict(prepare_list(storage_a, a_href_to_uid))
    list_b = dict(prepare_list(storage_b, b_href_to_uid))
    a_uid_to_href = dict((x['uid'], href) for href, x in list_a.iteritems())
    b_uid_to_href = dict((x['uid'], href) for href, x in list_b.iteritems())
    del a_href_to_uid, b_href_to_uid

    actions, prefetch_from_a, prefetch_from_b = \
        get_actions(list_a, list_b, status, a_uid_to_href, b_uid_to_href)

    prefetch(storage_a, list_a, prefetch_from_a)
    prefetch(storage_b, list_b, prefetch_from_b)

    storages = {
        'a': (storage_a, list_a, a_uid_to_href),
        'b': (storage_b, list_b, b_uid_to_href),
        None: (None, None, None)
    }

    for action, uid, source, dest in actions:
        source_storage, source_list, source_uid_to_href = storages[source]
        dest_storage, dest_list, dest_uid_to_href = storages[dest]

        if action in ('upload', 'update'):
            source_href = source_uid_to_href[uid]
            source_etag = source_list[source_href]['etag']
            obj = source_list[source_href]['obj']

            if action == 'upload':
                dest_href, dest_etag = dest_storage.upload(obj)
            else:
                dest_href = dest_uid_to_href[uid]
                old_etag = dest_list[dest_href]['etag']
                dest_etag = dest_storage.update(dest_href, obj, old_etag)
            source_status = (source_href, source_etag)
            dest_status = (dest_href, dest_etag)
            status[uid] = source_status + dest_status if source == 'a' else \
                dest_status + source_status
        elif action == 'delete':
            if dest is not None:
                dest_href = dest_uid_to_href[uid]
                dest_etag = dest_list[dest_href]['etag']
                dest_storage.delete(dest_href, dest_etag)
            del status[uid]


def get_actions(list_a, list_b, status, a_uid_to_href, b_uid_to_href):
    prefetch_from_a = []
    prefetch_from_b = []
    actions = []
    uids_a = set(x['uid'] for x in list_a.values())
    uids_b = set(x['uid'] for x in list_b.values())
    uids_status = set(status)
    for uid in uids_a.union(uids_b).union(uids_status):
        href_a = a_uid_to_href.get(uid, None)
        href_b = b_uid_to_href.get(uid, None)
        a = list_a.get(href_a, None)
        b = list_b.get(href_b, None)
        if uid not in status:
            if uid in uids_a and uid in uids_b:  # missing status
                # TODO: might need some kind of diffing too?
                if a['obj'].raw != b['obj'].raw:
                    1 / 0
                status[uid] = (href_a, a['etag'], href_b, b['etag'])
            # new item was created in a
            elif uid in uids_a and uid not in uids_b:
                prefetch_from_a.append(href_a)
                actions.append(('upload', uid, 'a', 'b'))
            # new item was created in b
            elif uid not in uids_a and uid in uids_b:
                prefetch_from_b.append(href_b)
                actions.append(('upload', uid, 'b', 'a'))
        else:
            _, status_etag_a, _, status_etag_b = status[uid]
            if uid in uids_a and uid in uids_b:
                if a['etag'] != status_etag_a and b['etag'] != status_etag_b:
                    1 / 0  # conflict resolution TODO
                elif a['etag'] != status_etag_a:  # item was updated in a
                    prefetch_from_a.append(href_a)
                    actions.append(('update', uid, 'a', 'b'))
                elif b['etag'] != status_etag_b:  # item was updated in b
                    prefetch_from_b.append(href_b)
                    actions.append(('update', uid, 'b', 'a'))
                else:  # completely in sync!
                    pass
            elif uid in uids_a and uid not in uids_b:  # was deleted from b
                actions.append(('delete', uid, None, 'a'))
            elif uid not in uids_a and uid in uids_b:  # was deleted from a
                actions.append(('delete', uid, None, 'b'))
            # was deleted from a and b
            elif uid not in uids_a and uid not in uids_b:
                actions.append(('delete', uid, None, None))
    return actions, prefetch_from_a, prefetch_from_b
