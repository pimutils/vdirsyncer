# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.http
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import hashlib

from .base import Item, Storage
from ..utils import expand_path, get_password, request, text_type, urlparse

USERAGENT = 'vdirsyncer'


def split_simple_collection(lines):
    item = []
    collection_type = None
    item_type = None
    for line in lines:
        if u':' not in line:
            key = line
            value = None
        else:
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
                yield item
                item = []
                item_type = None
            else:
                item.append(line)
        else:
            if item_type is not None:
                item.append(line)


def wrap_items(items, collection_type, exclude=(u'VTIMEZONE',)):
    for item in items:
        key, value = (x.strip() for x in item[0].split(u':'))
        if value in exclude:
            yield item
        else:
            yield ([u'BEGIN:' + collection_type] + item +
                   [u'END:' + collection_type])


def inline_timezones(items):
    timezone = None
    for item in items:
        if u':' not in item[0]:
            import pdb
            pdb.set_trace()

        key, value = (x.strip() for x in item[0].split(u':'))
        if value == u'VTIMEZONE':
            if timezone is not None:
                raise ValueError('Multiple timezones.')
            timezone = item
        else:
            if timezone is not None:
                item = [item[0]] + timezone + item[1:]
            yield item


def split_collection(lines):
    collection_type = None
    for line in lines:
        key, value = (x.strip() for x in line.split(u':'))
        if key == u'BEGIN':
            collection_type = value
            break

    is_calendar = collection_type == u'VCALENDAR'
    rv = split_simple_collection(lines)

    if is_calendar:
        rv = inline_timezones(wrap_items(rv, collection_type))

    return rv


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
            'auth': prepare_auth(auth, username, password),
            'latin1_fallback': False
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
        for i, item in enumerate(split_collection(r.text.splitlines())):
            item = Item(u'\n'.join(item), needs_uid=False)
            etag = hashlib.sha256(item.raw.encode('utf-8')).hexdigest()
            if item.uid is None:
                item.uid = etag
            self._items[item.uid] = item, etag

        for href, (item, etag) in self._items.items():
            yield href, etag

    def get(self, href):
        return self._items[href]
