# -*- coding: utf-8 -*-

import os

from .. import StorageTests, get_server_mixin


dav_server = os.environ.get('DAV_SERVER', 'skip')
ServerMixin = get_server_mixin(dav_server)


class DAVStorageTests(ServerMixin, StorageTests):
    dav_server = dav_server

    def test_dav_empty_get_multi_performance(self, s, monkeypatch):
        def breakdown(*a, **kw):
            raise AssertionError('Expected not to be called.')

        monkeypatch.setattr('requests.sessions.Session.request', breakdown)

        try:
            assert list(s.get_multi([])) == []
        finally:
            # Make sure monkeypatch doesn't interfere with DAV server teardown
            monkeypatch.undo()
