# -*- coding: utf-8 -*-

import os

import requests
import requests.exceptions

from tests import assert_item_equals

import vdirsyncer.exceptions as exceptions
from vdirsyncer.storage.base import Item

from .. import StorageTests


dav_server = os.environ.get('DAV_SERVER', '').strip() or 'radicale'


def _get_server_mixin(server_name):
    from . import __name__ as base
    x = __import__('{}.servers.{}'.format(base, server_name), fromlist=[''])
    return x.ServerMixin

ServerMixin = _get_server_mixin(dav_server)


class DavStorageTests(ServerMixin, StorageTests):
    dav_server = dav_server

    def test_dav_broken_item(self, s):
        item = Item(u'HAHA:YES')
        try:
            s.upload(item)
        except (exceptions.Error, requests.exceptions.HTTPError):
            pass
        assert not list(s.list())

    def test_dav_empty_get_multi_performance(self, s, monkeypatch):
        def breakdown(*a, **kw):
            raise AssertionError('Expected not to be called.')

        monkeypatch.setattr('requests.sessions.Session.request', breakdown)

        assert list(s.get_multi([])) == []

    def test_dav_unicode_href(self, s, get_item, monkeypatch):
        if self.dav_server != 'radicale':
            # Radicale is unable to deal with unicode hrefs
            monkeypatch.setattr(s, '_get_href',
                                lambda item: item.ident + s.fileext)
        item = get_item(uid=u'lolätvdirsynceröü град сатану')
        href, etag = s.upload(item)
        item2, etag2 = s.get(href)
        assert_item_equals(item, item2)
