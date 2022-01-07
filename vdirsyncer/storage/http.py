import urllib.parse as urlparse

import aiohttp

from .. import exceptions
from ..http import USERAGENT
from ..http import prepare_auth
from ..http import prepare_client_cert
from ..http import prepare_verify
from ..http import request
from ..vobject import Item
from ..vobject import split_collection
from .base import Storage


class HttpStorage(Storage):
    storage_name = "http"
    read_only = True
    _repr_attributes = ["username", "url"]
    _items = None

    # Required for tests.
    _ignore_uids = True

    def __init__(
        self,
        url,
        username="",
        password="",
        verify=None,
        auth=None,
        useragent=USERAGENT,
        verify_fingerprint=None,
        auth_cert=None,
        *,
        connector,
        **kwargs
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
            self._settings["ssl"] = ssl

        self.username, self.password = username, password
        self.useragent = useragent
        assert connector is not None
        self.connector = connector

        collection = kwargs.get("collection")
        if collection is not None:
            url = urlparse.urljoin(url, collection)
        self.url = url
        self.parsed_url = urlparse.urlparse(self.url)

    def _default_headers(self):
        return {"User-Agent": self.useragent}

    async def list(self):
        async with aiohttp.ClientSession(
            connector=self.connector,
            connector_owner=False,
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

        for item in split_collection((await r.read()).decode("utf-8")):
            item = Item(item)
            if self._ignore_uids:
                item = item.with_uid(item.hash)

            self._items[item.ident] = item, item.hash

        for href, (_, etag) in self._items.items():
            yield href, etag

    async def get(self, href):
        if self._items is None:
            async for _ in self.list():
                pass

        try:
            return self._items[href]
        except KeyError:
            raise exceptions.NotFoundError(href)
