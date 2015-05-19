# -*- coding: utf-8 -*-

import random

import vdirsyncer.exceptions as exceptions
from vdirsyncer.storage.base import Storage


def _random_string():
    return '{:.9f}'.format(random.random())


class MemoryStorage(Storage):

    '''
    Saves data in RAM, only useful for testing.
    '''

    def __init__(self, fileext='', **kwargs):
        if kwargs.get('collection') is not None:
            raise ValueError('MemoryStorage does not support collections.')
        self.items = {}  # href => (etag, item)
        self.fileext = fileext
        super(MemoryStorage, self).__init__(**kwargs)

    def _get_href(self, item):
        return item.ident + self.fileext

    def list(self):
        for href, (etag, item) in self.items.items():
            yield href, etag

    def get(self, href):
        etag, item = self.items[href]
        return item, etag

    def has(self, href):
        return href in self.items

    def upload(self, item):
        href = self._get_href(item)
        if href in self.items:
            raise exceptions.AlreadyExistingError(item)
        etag = _random_string()
        self.items[href] = (etag, item)
        return href, etag

    def update(self, href, item, etag):
        if href not in self.items:
            raise exceptions.NotFoundError(href)
        actual_etag, _ = self.items[href]
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        new_etag = _random_string()
        self.items[href] = (new_etag, item)
        return new_etag

    def delete(self, href, etag):
        if not self.has(href):
            raise exceptions.NotFoundError(href)
        if etag != self.items[href][0]:
            raise exceptions.WrongEtagError(etag)
        del self.items[href]
