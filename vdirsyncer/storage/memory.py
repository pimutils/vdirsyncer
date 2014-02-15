# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.memory
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import datetime
from vdirsyncer.storage.base import Item, Storage 
import vdirsyncer.exceptions as exceptions

class MemoryStorage(Storage):
    '''
    Saves data in RAM, only useful for testing.
    '''
    def __init__(self, **kwargs):
        self.items = {}  # uid => (etag, object)
        super(MemoryStorage, self).__init__(**kwargs)

    def list_items(self):
        for uid, (etag, obj) in self.items.items():
            yield uid, etag

    def get_items(self, uids):
        for uid in uids:
            etag, obj = self.items[uid]
            yield obj, uid, etag

    def item_exists(self, uid):
        return uid in self.items

    def upload(self, obj):
        if obj.uid in self.items:
            raise exceptions.AlreadyExistingError(obj)
        etag = datetime.datetime.now()
        self.items[obj.uid] = (etag, obj)
        return etag

    def update(self, obj, etag):
        if obj.uid not in self.items:
            raise exceptions.NotFoundError(obj)
        etag = datetime.datetime.now()
        self.items[obj.uid] = (etag, obj)
        return etag

    def delete(self, uid):
        del self.items[uid]
