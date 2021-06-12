import urllib.parse as urlparse

from .. import exceptions
from ..http import prepare_auth
from ..http import prepare_client_cert
from ..http import prepare_verify
from ..http import request
from ..http import USERAGENT
from ..vobject import Item
from ..vobject import split_collection
from .base import Storage


class HttpStorage(Storage):
    storage_name = "http"
    read_only = True
    _repr_attributes = ("username", "url")
    _items = None

    # Required for tests.
    _ignore_uids = True

    def __init__(
        self,
        url,
        username="",
        password="",
        verify=True,
        auth=None,
        useragent=USERAGENT,
        verify_fingerprint=None,
        auth_cert=None,
        **kwargs
    ):
        super().__init__(**kwargs)

        self._settings = {
            "auth": prepare_auth(auth, username, password),
            "cert": prepare_client_cert(auth_cert),
            "latin1_fallback": False,
        }
        self._settings.update(prepare_verify(verify, verify_fingerprint))

        self.username, self.password = username, password
        self.useragent = useragent

        collection = kwargs.get("collection")
        if collection is not None:
            url = urlparse.urljoin(url, collection)
        self.url = url
        self.parsed_url = urlparse.urlparse(self.url)

    def _default_headers(self):
        return {"User-Agent": self.useragent}

    def list(self):
        r = request("GET", self.url, headers=self._default_headers(), **self._settings)
        self._items = {}

        for item in split_collection(r.text):
            item = Item(item)
            if self._ignore_uids:
                item = item.with_uid(item.hash)

            self._items[item.ident] = item, item.hash

        return ((href, etag) for href, (item, etag) in self._items.items())

    def get(self, href):
        if self._items is None:
            self.list()

        try:
            return self._items[href]
        except KeyError:
            raise exceptions.NotFoundError(href)
