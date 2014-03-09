
# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.http
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import requests
import hashlib
from .base import Storage, Item


def split_collection(text):
    item = []
    collection_type = None
    item_type = None
    for line in text.splitlines():
        if not line.strip():
            continue
        key, value = (x.strip() for x in line.split(u':', 1))
        if key == u'BEGIN':
            if collection_type is None:
                collection_type = value
            elif item_type is None:
                item_type = value
                item.append(line)
            else:
                item.append(line)
        elif key == u'END':
            if value == collection_type:
                break
            elif value == item_type:
                item.append(line)
                yield Item(u'\n'.join(item))
                item = []
            else:
                item.append(line)
        else:
            if item_type is not None:
                item.append(line)


class HttpStorage(Storage):
    _repr_attributes = ('url',)
    _items = None

    def __init__(self, url, **kwargs):
        super(HttpStorage, self).__init__(**kwargs)
        self.url = url

    def list(self):
        if self._items is None:
            r = requests.get(self.url)
            r.raise_on_status()
            self._items = {}
            for item in split_collection(r.text):
                self._items[item.uid] = item

        for uid, item in self._items.items():
            yield uid, hashlib.sha256(item.raw)

    def get(self, href):
        x = self._items[href]
        return x, hashlib.sha256(x.raw)

    def has(self, href):
        return href in self._items
