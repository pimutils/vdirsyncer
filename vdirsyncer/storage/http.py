
# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.http
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import requests
import urlparse
import hashlib
from .base import Storage, Item
from vdirsyncer.utils import expand_path


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


def prepare_auth(auth, username, password):
    if (username and password) or auth == 'basic':
        return (username, password)
    elif auth == 'digest':
        from requests.auth import HTTPDigestAuth
        return HTTPDigestAuth(username, password)
    elif auth is None:
        return None
    else:
        raise ValueError('Unknown authentication method: {}'.format(auth))


def prepare_verify(verify):
    if isinstance(verify, bool):
        return verify
    return expand_path(verify)


class HttpStorageBase(Storage):
    _repr_attributes = ('username', 'url')
    _items = None

    def __init__(self, url, username='', password='', collection=None,
                 verify=True, auth=None, useragent='vdirsyncer', **kwargs):

        super(HttpStorageBase, self).__init__(**kwargs)

        self._settings = {
            'verify': prepare_verify(verify),
            'auth': prepare_auth(auth, username, password)
        }
        self.username, self.password = username, password
        self.useragent = useragent

        url = url.rstrip('/') + '/'
        if collection is not None:
            url = urlparse.urljoin(url, collection)
        self.url = url.rstrip('/') + '/'
        self.parsed_url = urlparse.urlparse(self.url)
        self.collection = collection

    def _default_headers(self):
        return {
            'User-Agent': self.useragent,
            'Content-Type': 'application/xml; charset=UTF-8'
        }


class HttpStorage(HttpStorageBase):
    def list(self):
        if self._items is None:
            r = requests.get(self.url, **self._settings)
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
