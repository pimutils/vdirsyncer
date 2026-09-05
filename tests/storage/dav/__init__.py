from __future__ import annotations

import os
import re
import uuid
import xml.etree.ElementTree as ET

import aiohttp
import aiostream
import pytest
from aioresponses import aioresponses

from tests import assert_item_equals
from tests.storage import StorageTests
from tests.storage import get_server_mixin
from vdirsyncer import exceptions
from vdirsyncer.vobject import Item

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
        href, _etag = await s.upload(item)
        item2, _etag2 = await s.get(href)
        assert_item_equals(item, item2)

    @pytest.mark.asyncio
    async def test_dav_get_multi_missing_href_batch_is_nonfatal(
        self, s, get_item, monkeypatch
    ):
        item = get_item()
        existing_href, _etag = await s.upload(item)
        missing_href = existing_href + ".missing"

        def _fake_parse_prop_responses(_root):
            prop = ET.Element("prop")
            ET.SubElement(prop, s.get_multi_data_query).text = item.raw
            return [(existing_href, '"etag-existing"', prop)]

        monkeypatch.setattr(s, "_parse_prop_responses", _fake_parse_prop_responses)
        url = str(s.url).rstrip("/")
        url_pattern = re.compile(rf"^{re.escape(url)}/?$")
        with aioresponses() as m:
            m.add(url_pattern, method="REPORT", status=207, body="<multistatus/>")
            result = await aiostream.stream.list(
                s.get_multi([existing_href, missing_href])
            )
        assert len(m.requests) == 1
        assert len(result) == 1
        href, returned_item, etag = result[0]
        assert href == existing_href
        assert etag == '"etag-existing"'
        assert_item_equals(item, returned_item)

    @pytest.mark.asyncio
    async def test_dav_get_multi_missing_single_href_raises(
        self, s, get_item, monkeypatch
    ):
        existing_href, _etag = await s.upload(get_item())
        href = existing_href + ".missing"

        def _fake_parse_prop_responses(_root):
            return []

        monkeypatch.setattr(s, "_parse_prop_responses", _fake_parse_prop_responses)
        url = str(s.url).rstrip("/")
        url_pattern = re.compile(rf"^{re.escape(url)}/?$")
        with aioresponses() as m:
            m.add(url_pattern, method="REPORT", status=207, body="<multistatus/>")
            with pytest.raises(exceptions.NotFoundError):
                await aiostream.stream.list(s.get_multi([href]))
        assert len(m.requests) == 1
