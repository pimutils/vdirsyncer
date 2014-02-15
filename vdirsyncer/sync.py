def sync(storage_a, storage_b, status):
    '''Syncronizes two storages.

    :param storage_a: The first storage
    :param storage_b: The second storage
    :param status: {uid: (etag_a, etag_b)}
    '''
    items_a = dict(storage_a.list_items())
    items_b = dict(storage_b.list_items())
    downloads_a = set()  # uids which to copy from a to b
    downloads_b = set()  # uids which to copy from b to a
    deletes_a = set()
    deletes_b = set()

    for uid in set(items_a) + set(items_b):
        if uid not in status:
            if uid in items_a and uid in items_b:  # missing status
                status[uid] = (items_a[uid], items_b[uid])  # TODO: might need etag diffing too?
            elif uid in items_a and uid not in items_b:  # new item in a
                downloads_a.add(uid)
            elif uid not in items_a and uid in items_b:  # new item in b
                downloads_b.add(uid)
        else:
            if uid in items_a and uid in items_b:
                if items_a[uid] != status[uid][0] and items_a[uid] != status[uid][1]:
                    1/0  # conflict resolution
                elif items_a[uid] != status[uid][0]:  # item update in a
                    downloads_a.add(uid)
                elif items_b[uid] != status[uid][1]:  # item update in b
                    downloads_b.add(uid)
                else:  # completely in sync!
                    pass
            elif uid in items_a and uid not in items_b:  # deleted from b
                deletes_a.add(uid)
            elif uid not in items_a and uid in items_b:  # deleted from a
                deletes_b.add(uid)
