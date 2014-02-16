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

    def list(self):
        for uid, (etag, obj) in self.items.items():
            yield uid, etag

    def get(self, uid):
        etag, obj = self.items[uid]
        return obj, etag

    def has(self, uid):
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
        actual_etag, _ = self.items[obj.uid]
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        new_etag = datetime.datetime.now()
        self.items[obj.uid] = (new_etag, obj)
        return etag

    def delete(self, uid, etag):
        if not self.has(uid):
            raise exceptions.NotFoundError(uid)
        if etag != self.items[uid][0]:
            raise exceptions.WrongEtagError(etag)
        del self.items[uid]
