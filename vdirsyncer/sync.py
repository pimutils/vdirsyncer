def sync(storage_a, storage_b, status):
    '''Syncronizes two storages.

    :param storage_a: The first storage
    :param storage_b: The second storage
    :param status: {uid: (etag_a, etag_b)}
    '''
    list_a = dict(storage_a.list_items())
    list_b = dict(storage_b.list_items())

    prefetch_items_from_a = []
    prefetch_items_from_b = []
    actions = []  # list(tuple(action, uid, source, dest))

    for uid in set(list_a).union(set(list_b)):
        if uid not in status:
            if uid in list_a and uid in list_b:  # missing status
                status[uid] = (list_a[uid], list_b[uid])  # TODO: might need etag diffing too?
            elif uid in list_a and uid not in list_b:  # new item in a
                prefetch_items_from_a.append(uid)
                actions.append(('upload', uid, 'a', 'b'))
            elif uid not in list_a and uid in list_b:  # new item in b
                prefetch_items_from_b.append(uid)
                actions.append(('upload', uid, 'b', 'a'))
        else:
            if uid in list_a and uid in list_b:
                if list_a[uid] != status[uid][0] and list_b[uid] != status[uid][1]:
                    1/0  # conflict resolution TODO
                elif list_a[uid] != status[uid][0]:  # item update in a
                    prefetch_items_from_a.append(uid)
                    actions.append(('update', uid, 'a', 'b'))
                elif list_b[uid] != status[uid][1]:  # item update in b
                    prefetch_items_from_b.append(uid)
                    actions.append(('update', uid, 'b', 'a'))
                else:  # completely in sync!
                    pass
            elif uid in list_a and uid not in list_b:  # deleted from b
                actions.append(('delete', uid, 'b', 'a'))
            elif uid not in list_a and uid in list_b:  # deleted from a
                actions.append(('delete', uid, 'a', 'b'))

    items_a = {}
    items_b = {}
    for item, uid, etag in storage_a.get_items(prefetch_items_from_a):
        items_a[uid] = (item, etag)
    for item, uid, etag in storage_b.get_items(prefetch_items_from_b):
        items_b[uid] = (item, etag)

    for action, uid, source, dest in actions:
        source_storage = storage_a if source == 'a' else storage_b
        dest_storage = storage_a if dest == 'a' else storage_b
        source_items = items_a if source == 'a' else items_b
        if action in ('upload', 'update'):
            item, source_etag = source_items[uid]
            if action == 'upload':
                dest_etag = dest_storage.upload(item)
            else:
                dest_etag = dest_storage.update(item, etag)
            status[uid] = (source_etag, dest_etag) if source == 'a' else (dest_etag, source_etag)
        elif action == 'delete':
            dest_storage.delete(uid)
            del status[uid]
