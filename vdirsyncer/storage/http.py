# -*- coding: utf-8 -*-

import urllib.parse as urlparse

from .base import Storage
from .. import exceptions
from ..http import HTTP_STORAGE_PARAMETERS, USERAGENT, prepare_auth, \
    prepare_client_cert, prepare_verify, request
from ..vobject import Item, split_collection


class HttpStorage(Storage):
    __doc__ = '''
    Use a simple ``.ics`` file (or similar) from the web.
    ``webcal://``-calendars are supposed to be used with this, but you have to
    replace ``webcal://`` with ``http://``, or better, ``https://``.

    Too many WebCAL providers generate UIDs of all ``VEVENT``-components
    on-the-fly, i.e. all UIDs change every time the calendar is downloaded.
    This leads many synchronization programs to believe that all events have
    been deleted and new ones created, and accordingly causes a lot of
    unnecessary uploads and deletions on the other side. Vdirsyncer completely
    ignores UIDs coming from :storage:`http` and will replace them with a hash
    of the normalized item content.

    :param url: URL to the ``.ics`` file.
    ''' + HTTP_STORAGE_PARAMETERS + '''

    A simple example::

        [pair holidays]
        a = holidays_local
        b = holidays_remote
        collections = null

        [storage holidays_local]
        type = "filesystem"
        path = ~/.config/vdir/calendars/holidays/
        fileext = .ics

        [storage holidays_remote]
        type = "http"
        url = https://example.com/holidays_from_hicksville.ics
    '''

    storage_name = 'http'
    read_only = True
    _repr_attributes = ('username', 'url')
    _items = None

    # Required for tests.
    _ignore_uids = True

    def __init__(self, url, username='', password='', verify=True, auth=None,
                 useragent=USERAGENT, verify_fingerprint=None, auth_cert=None,
                 **kwargs):
        super(HttpStorage, self).__init__(**kwargs)

        self._settings = {
            'auth': prepare_auth(auth, username, password),
            'cert': prepare_client_cert(auth_cert),
            'latin1_fallback': False,
        }
        self._settings.update(prepare_verify(verify, verify_fingerprint))

        self.username, self.password = username, password
        self.useragent = useragent

        collection = kwargs.get('collection')
        if collection is not None:
            url = urlparse.urljoin(url, collection)
        self.url = url
        self.parsed_url = urlparse.urlparse(self.url)

    def _default_headers(self):
        return {'User-Agent': self.useragent}

    def list(self):
        r = request('GET', self.url, headers=self._default_headers(),
                    **self._settings)
        self._items = {}

        for item in split_collection(r.text):
            item = Item(item)
            if self._ignore_uids:
                item = item.with_uid(item.hash)

            self._items[item.ident] = item, item.hash

        return ((href, etag) for href, (item, etag) in self._items.items())

    def get(self, href):
        if self._items is None:
            self.list()

        try:
            return self._items[href]
        except KeyError:
            raise exceptions.NotFoundError(href)
