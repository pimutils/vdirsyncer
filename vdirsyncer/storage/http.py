# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.http
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

from .base import Item, Storage
from ..exceptions import NotFoundError
from ..utils import expand_path, get_password, request
from ..utils.compat import iteritems, text_type, urlparse
from ..utils.vobject import split_collection

USERAGENT = 'vdirsyncer'


def prepare_auth(auth, username, password):
    if username and password:
        if auth == 'basic':
            return (username, password)
        elif auth == 'digest':
            from requests.auth import HTTPDigestAuth
            return HTTPDigestAuth(username, password)
        elif auth == 'guess' or auth is None:
            import requests_toolbelt
            if not hasattr(requests_toolbelt, 'GuessAuth'):
                raise RuntimeError('Your version of requests_toolbelt is too '
                                   'old.')
            return requests_toolbelt.GuessAuth(username, password)
        else:
            raise ValueError('Unknown authentication method: {}'.format(auth))
    elif auth:
        raise ValueError('For {} authentication, you need to specify username '
                         'and password.'.format(auth))
    else:
        return None


def prepare_verify(verify):
    if isinstance(verify, (text_type, bytes)):
        return expand_path(verify)
    return verify


class HttpStorage(Storage):
    '''
    Use a simple ``.ics`` file (or similar) from the web. Usable as ``http`` in
    the config file.

    :param url: URL to the ``.ics`` file.
    :param username: Username for authentication.
    :param password: Password for authentication.
    :param verify: Verify SSL certificate, default True. This can also be a
        local path to a self-signed SSL certificate.
    :param auth: Optional. Either ``basic``, ``digest`` or ``guess``. Default
        ``guess``. If you know yours, consider setting it explicitly for
        performance.
    :param useragent: Default ``vdirsyncer``.

    A simple example::

        [pair holidays]
        a = holidays_local
        b = holidays_remote

        [storage holidays_local]
        type = filesystem
        path = ~/.config/vdir/calendars/holidays/
        fileext = .ics

        [storage holidays_remote]
        type = http
        url = https://example.com/holidays_from_hicksville.ics
    '''

    storage_name = 'http'
    read_only = True
    _repr_attributes = ('username', 'url')
    _items = None

    def __init__(self, url, username='', password='', collection=None,
                 verify=True, auth=None, useragent=USERAGENT, **kwargs):
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

    def _default_headers(self):
        return {'User-Agent': self.useragent}

    def list(self):
        r = request('GET', self.url, **self._settings)
        self._items = {}

        for item in split_collection(r.text):
            item = Item(item)
            etag = item.hash
            self._items[item.ident] = item, etag

        return ((href, etag) for href, (item, etag) in iteritems(self._items))

    def get(self, href):
        if self._items is None:
            self.list()

        try:
            return self._items[href]
        except KeyError:
            raise NotFoundError(href)
