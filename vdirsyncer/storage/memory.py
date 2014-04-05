# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.memory
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import random
from vdirsyncer.storage.base import Storage
import vdirsyncer.exceptions as exceptions


def _get_etag():
    return '{:.9f}'.format(random.random())


class MemoryStorage(Storage):

    '''
    Saves data in RAM, only useful for testing.
    '''

    def __init__(self, **kwargs):
        self.items = {}  # href => (etag, item)
        super(MemoryStorage, self).__init__(**kwargs)

    def list(self):
        for href, (etag, item) in self.items.items():
            yield href, etag

    def get(self, href):
        etag, item = self.items[href]
        return item, etag

    def has(self, href):
        return href in self.items

    def upload(self, item):
        href = self._get_href(item.uid)
        if href in self.items:
            raise exceptions.AlreadyExistingError(item.uid)
        etag = _get_etag()
        self.items[href] = (etag, item)
        return href, etag

    def update(self, href, item, etag):
        if href != self._get_href(item.uid) or href not in self.items:
            raise exceptions.NotFoundError(href)
        actual_etag, _ = self.items[href]
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        new_etag = _get_etag()
        self.items[href] = (new_etag, item)
        return new_etag

    def delete(self, href, etag):
        if not self.has(href):
            raise exceptions.NotFoundError(href)
        if etag != self.items[href][0]:
            raise exceptions.WrongEtagError(etag)
        del self.items[href]
