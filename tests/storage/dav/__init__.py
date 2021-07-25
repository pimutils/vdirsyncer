import os
import uuid

import aiohttp
import aiostream
import pytest

from tests import assert_item_equals
from vdirsyncer import exceptions
from vdirsyncer.vobject import Item

from .. import StorageTests
from .. import get_server_mixin

dav_server = os.environ.get("DAV_SERVER", "skip")
ServerMixin = get_server_mixin(dav_server)


class DAVStorageTests(ServerMixin, StorageTests):
    dav_server = dav_server

    @pytest.mark.skipif(dav_server == "radicale", reason="Radicale is very tolerant.")
    @pytest.mark.asyncio
    async def test_dav_broken_item(self, s):
        item = Item("HAHA:YES")
        with pytest.raises((exceptions.Error, aiohttp.ClientResponseError)):
            await s.upload(item)
        assert not await aiostream.stream.list(s.list())

    @pytest.mark.asyncio
    async def test_dav_empty_get_multi_performance(self, s, monkeypatch):
        def breakdown(*a, **kw):
            raise AssertionError("Expected not to be called.")

        monkeypatch.setattr("requests.sessions.Session.request", breakdown)

        try:
            assert list(await aiostream.stream.list(s.get_multi([]))) == []
        finally:
            # Make sure monkeypatch doesn't interfere with DAV server teardown
            monkeypatch.undo()

    @pytest.mark.asyncio
    async def test_dav_unicode_href(self, s, get_item, monkeypatch):
        if self.dav_server == "radicale":
            pytest.skip("Radicale is unable to deal with unicode hrefs")

        monkeypatch.setattr(s, "_get_href", lambda item: item.ident + s.fileext)
        item = get_item(uid="град сатану" + str(uuid.uuid4()))
        href, etag = await s.upload(item)
        item2, etag2 = await s.get(href)
        assert_item_equals(item, item2)
