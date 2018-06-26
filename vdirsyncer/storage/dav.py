# -*- coding: utf-8 -*-

import datetime
import logging
import urllib.parse as urlparse
import xml.etree.ElementTree as etree

import requests
from requests.exceptions import HTTPError

from ._rust import RustStorage
from .. import exceptions, http, native, utils
from ..http import USERAGENT, prepare_auth, \
    prepare_client_cert


class DAVStorage(RustStorage):
    # the file extension of items. Useful for testing against radicale.
    fileext = None
    # mimetype of items
    item_mimetype = None

    _repr_attributes = ('username', 'url')


class CalDAVStorage(DAVStorage):
    storage_name = 'caldav'
    fileext = '.ics'
    item_mimetype = 'text/calendar'

    start_date = None
    end_date = None

    def __init__(self, url, username=None, password=None, useragent=None,
                 verify_cert=None, auth_cert=None, start_date=None,
                 end_date=None, item_types=(), **kwargs):
        super(CalDAVStorage, self).__init__(**kwargs)

        # defined for _repr_attributes
        self.username = kwargs.get('username')
        self.url = kwargs.get('url')

        item_types = item_types or ()
        if not isinstance(item_types, (list, tuple)):
            raise exceptions.UserError('item_types must be a list.')
        if not isinstance(url, str):
            raise exceptions.UserError('Url must be a string')

        self.item_types = tuple(x.upper() for x in item_types)
        if (start_date is None) != (end_date is None):
            raise exceptions.UserError('If start_date is given, '
                                       'end_date has to be given too.')
        elif start_date is not None and end_date is not None:
            namespace = dict(datetime.__dict__)
            namespace['start_date'] = self.start_date = \
                (eval(start_date, namespace)
                 if isinstance(start_date, (bytes, str))
                 else start_date)
            self.end_date = \
                (eval(end_date, namespace)
                 if isinstance(end_date, (bytes, str))
                 else end_date)

        self._native_storage = native.ffi.gc(
            native.lib.vdirsyncer_init_caldav(
                url.encode('utf-8'),
                (username or '').encode('utf-8'),
                (password or '').encode('utf-8'),
                (useragent or '').encode('utf-8'),
                (verify_cert or '').encode('utf-8'),
                (auth_cert or'').encode('utf-8'),
                int(self.start_date.timestamp()) if self.start_date else -1,
                int(self.end_date.timestamp()) if self.end_date else -1,
                'VEVENT' in item_types,
                'VJOURNAL' in item_types,
                'VTODO' in item_types
            ),
            native.lib.vdirsyncer_storage_free
        )


class CardDAVStorage(DAVStorage):
    storage_name = 'carddav'
    fileext = '.vcf'
    item_mimetype = 'text/vcard'

    def __init__(self, url, username=None, password=None, useragent=None,
                 verify_cert=None, auth_cert=None, **kwargs):
        super(CardDAVStorage, self).__init__(**kwargs)

        # defined for _repr_attributes
        self.username = kwargs.get('username')
        self.url = kwargs.get('url')

        if not isinstance(url, str):
            raise exceptions.UserError('Url must be a string')

        self._native_storage = native.ffi.gc(
            native.lib.vdirsyncer_init_carddav(
                url.encode('utf-8'),
                (username or '').encode('utf-8'),
                (password or '').encode('utf-8'),
                (useragent or '').encode('utf-8'),
                (verify_cert or '').encode('utf-8'),
                (auth_cert or '').encode('utf-8')
            ),
            native.lib.vdirsyncer_storage_free
        )

        super(CardDAVStorage, self).__init__(**kwargs)
