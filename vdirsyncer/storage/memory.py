# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.memory
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import datetime
from vdirsyncer.storage.base import Storage
import vdirsyncer.exceptions as exceptions


class MemoryStorage(Storage):

    '''
    Saves data in RAM, only useful for testing.
    '''

    def __init__(self, **kwargs):
        self.items = {}  # href => (etag, object)
        super(MemoryStorage, self).__init__(**kwargs)

    def list(self):
        for href, (etag, obj) in self.items.items():
            yield href, etag

    def get(self, href):
        etag, obj = self.items[href]
        return obj, etag

    def has(self, href):
        return href in self.items

    def upload(self, obj):
        href = self._get_href(obj.uid)
        if href in self.items:
            raise exceptions.AlreadyExistingError(obj.uid)
        etag = datetime.datetime.now()
        self.items[href] = (etag, obj)
        return href, etag

    def update(self, href, obj, etag):
        if href != self._get_href(obj.uid) or href not in self.items:
            raise exceptions.NotFoundError(href)
        actual_etag, _ = self.items[href]
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        new_etag = datetime.datetime.now()
        self.items[href] = (new_etag, obj)
        return new_etag

    def delete(self, href, etag):
        if not self.has(href):
            raise exceptions.NotFoundError(href)
        if etag != self.items[href][0]:
            raise exceptions.WrongEtagError(etag)
        del self.items[href]
