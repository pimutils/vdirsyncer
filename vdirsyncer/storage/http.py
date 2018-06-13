# -*- coding: utf-8 -*-

from .base import Storage
from ._rust import RustStorageMixin
from .. import exceptions, native
from ..http import USERAGENT


class HttpStorage(RustStorageMixin, Storage):

    storage_name = 'http'
    read_only = True
    _repr_attributes = ('username', 'url')
    _items = None

    # Required for tests.
    _ignore_uids = True

    def __init__(self, url, username='', password='', useragent=USERAGENT,
                 verify_cert=None, auth_cert=None, **kwargs):
        if kwargs.get('collection') is not None:
            raise exceptions.UserError('HttpStorage does not support '
                                       'collections.')

        assert auth_cert is None, "not yet supported"

        super(HttpStorage, self).__init__(**kwargs)

        self._native_storage = native.ffi.gc(
            native.lib.vdirsyncer_init_http(
                url.encode('utf-8'),
                (username or "").encode('utf-8'),
                (password or "").encode('utf-8'),
                (useragent or "").encode('utf-8'),
                (verify_cert or "").encode('utf-8'),
                (auth_cert or "").encode('utf-8')
            ),
            native.lib.vdirsyncer_storage_free
        )

        self.username = username
        self.url = url
