from __future__ import annotations

import logging
import subprocess
import urllib.parse as urlparse
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from vdirsyncer import exceptions
from vdirsyncer.http import USERAGENT
from vdirsyncer.http import prepare_auth
from vdirsyncer.http import prepare_client_cert
from vdirsyncer.http import prepare_verify
from vdirsyncer.http import request
from vdirsyncer.vobject import Item
from vdirsyncer.vobject import split_collection

from .base import Storage

logger = logging.getLogger(__name__)


class HttpStorage(Storage):
    storage_name = "http"
    read_only = True
    _repr_attributes = ("username", "url")
    _items: dict[str, tuple[Item, str]] | None = None

    # Required for tests.
    _ignore_uids = True

    def __init__(
        self,
        url: str,
        username: str = "",
        password: str = "",
        verify: Any = None,
        auth: Any = None,
        useragent: str = USERAGENT,
        verify_fingerprint: str | None = None,
        auth_cert: Any = None,
        filter_hook: str | None = None,
        *,
        connector: aiohttp.BaseConnector,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self._settings = {
            "cert": prepare_client_cert(auth_cert),
            "latin1_fallback": False,
        }
        auth = prepare_auth(auth, username, password)
        if auth:
            self._settings["auth"] = auth

        ssl = prepare_verify(verify, verify_fingerprint)
        if ssl:
            self._settings["ssl"] = ssl  # type: ignore[assignment]

        self.username, self.password = username, password
        self.useragent = useragent
        assert connector is not None
        self.connector = connector
        self._filter_hook = filter_hook

        collection = kwargs.get("collection")
        if collection is not None:
            url = urlparse.urljoin(url, collection)
        self.url = url
        self.parsed_url = urlparse.urlparse(self.url)

    def _default_headers(self) -> dict[str, str]:
        return {"User-Agent": self.useragent}

    def _run_filter_hook(self, raw_item: str) -> str:
        assert self._filter_hook is not None
        try:
            result = subprocess.run(
                [self._filter_hook],
                input=raw_item,
                capture_output=True,
                encoding="utf-8",
            )
            return result.stdout
        except OSError as e:
            logger.warning(f"Error executing external command: {e!s}")
            return raw_item

    async def list(self) -> AsyncIterator[tuple[str, str]]:
        async with aiohttp.ClientSession(
            connector=self.connector,
            connector_owner=False,
            trust_env=True,
            # TODO use `raise_for_status=true`, though this needs traces first,
        ) as session:
            r = await request(
                "GET",
                self.url,
                headers=self._default_headers(),
                session=session,
                **self._settings,
            )
        self._items = {}

        for raw_item in split_collection((await r.read()).decode("utf-8")):
            if self._filter_hook:
                raw_item = self._run_filter_hook(raw_item)
            if not raw_item:
                continue

            item = Item(raw_item)
            if self._ignore_uids:
                item = item.with_uid(item.hash)

            self._items[item.ident] = item, item.hash

        for href, (_, etag) in self._items.items():
            yield href, etag

    async def get(self, href: str) -> tuple[Item, str]:
        if self._items is None:
            async for _ in self.list():
                pass

        assert self._items is not None  # type assertion
        try:
            return self._items[href]
        except KeyError:
            raise exceptions.NotFoundError(href)
