# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.http
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import hashlib
from .base import Storage, Item
from vdirsyncer.utils import expand_path, get_password, request, urlparse, \
    text_type

USERAGENT = 'vdirsyncer'


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
    if isinstance(verify, (text_type, bytes)):
        return expand_path(verify)
    return verify


class HttpStorage(Storage):
    _repr_attributes = ('username', 'url')

    def __init__(self, url, username='', password='', collection=None,
                 verify=True, auth=None, useragent=USERAGENT, **kwargs):
        '''
        :param url: Base URL or an URL to a collection. Autodiscovery should be
            done via :py:meth:`DavStorage.discover`.
        :param username: Username for authentication.
        :param password: Password for authentication.
        :param verify: Verify SSL certificate, default True.
        :param auth: Authentication method, from {'basic', 'digest'}, default
            'basic'.
        :param useragent: Default 'vdirsyncer'.
        '''
        super(HttpStorage, self).__init__(**kwargs)

        if username and not password:
            password = get_password(username, url)

        self._settings = {
            'verify': prepare_verify(verify),
            'auth': prepare_auth(auth, username, password)
        }
        self.username, self.password = username, password
        self.useragent = useragent

        if collection is not None:
            url = urlparse.urljoin(url, collection)
        self.url = url
        self.parsed_url = urlparse.urlparse(self.url)
        self.collection = collection
        self._items = {}

    def _default_headers(self):
        return {'User-Agent': self.useragent}

    def list(self):
        r = request('GET', self.url, **self._settings)
        r.raise_for_status()
        self._items.clear()
        for i, item in enumerate(split_collection(r.text)):
            uid = item.uid if item.uid is not None else i
            self._items[uid] = item

        for uid, item in self._items.items():
            yield uid, hashlib.sha256(item.raw.encode('utf-8')).hexdigest()

    def get(self, href):
        x = self._items[href]
        return x, hashlib.sha256(x.raw.encode('utf-8')).hexdigest()
