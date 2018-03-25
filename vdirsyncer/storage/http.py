# -*- coding: utf-8 -*-

import urllib.parse as urlparse

from .base import Storage
from ._rust import RustStorageMixin
from .. import exceptions, native
from ..http import USERAGENT, prepare_auth, \
    prepare_client_cert, prepare_verify, request
from ..vobject import Item, split_collection


class HttpStorage(RustStorageMixin, Storage):
    storage_name = 'http'
    read_only = True
    _repr_attributes = ('username', 'url')
    _items = None

    # Required for tests.
    _ignore_uids = True

    def __init__(self, url, username='', password='', verify=True, auth=None,
                 useragent=USERAGENT, verify_fingerprint=None, auth_cert=None,
                 **kwargs):
        if kwargs.get('collection') is not None:
            raise exceptions.UserError('HttpStorage does not support '
                                       'collections.')

        assert verify, "not yet supported" # TODO
        assert auth is None, "not yet supported" # TODO
        assert useragent == USERAGENT, "not yet supported" # TODO
        assert verify_fingerprint is None, "not yet supported" # TODO
        assert auth_cert is None, "not yet supported" # TODO

        super(HttpStorage, self).__init__(**kwargs)

        self._native_storage = native.ffi.gc(
            native.lib.vdirsyncer_init_http(
                url.encode('utf-8'),
                (username or "").encode('utf-8'),
                (password or "").encode('utf-8')
            ),
            native.lib.vdirsyncer_storage_free
        )

        self.username = username
        self.url = url
