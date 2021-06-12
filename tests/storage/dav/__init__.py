import os
import uuid

import pytest
import requests.exceptions

from .. import get_server_mixin
from .. import StorageTests
from tests import assert_item_equals
from vdirsyncer import exceptions
from vdirsyncer.vobject import Item


dav_server = os.environ.get("DAV_SERVER", "skip")
ServerMixin = get_server_mixin(dav_server)


class DAVStorageTests(ServerMixin, StorageTests):
    dav_server = dav_server

    @pytest.mark.skipif(dav_server == "radicale", reason="Radicale is very tolerant.")
    def test_dav_broken_item(self, s):
        item = Item("HAHA:YES")
        with pytest.raises((exceptions.Error, requests.exceptions.HTTPError)):
            s.upload(item)
        assert not list(s.list())

    def test_dav_empty_get_multi_performance(self, s, monkeypatch):
        def breakdown(*a, **kw):
            raise AssertionError("Expected not to be called.")

        monkeypatch.setattr("requests.sessions.Session.request", breakdown)

        try:
            assert list(s.get_multi([])) == []
        finally:
            # Make sure monkeypatch doesn't interfere with DAV server teardown
            monkeypatch.undo()

    def test_dav_unicode_href(self, s, get_item, monkeypatch):
        if self.dav_server == "radicale":
            pytest.skip("Radicale is unable to deal with unicode hrefs")

        monkeypatch.setattr(s, "_get_href", lambda item: item.ident + s.fileext)
        item = get_item(uid="град сатану" + str(uuid.uuid4()))
        href, etag = s.upload(item)
        item2, etag2 = s.get(href)
        assert_item_equals(item, item2)
