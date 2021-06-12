import random

from .. import exceptions
from .base import normalize_meta_value
from .base import Storage


def _random_string():
    return f"{random.random():.9f}"


class MemoryStorage(Storage):

    storage_name = "memory"

    """
    Saves data in RAM, only useful for testing.
    """

    def __init__(self, fileext="", **kwargs):
        if kwargs.get("collection") is not None:
            raise exceptions.UserError("MemoryStorage does not support " "collections.")
        self.items = {}  # href => (etag, item)
        self.metadata = {}
        self.fileext = fileext
        super().__init__(**kwargs)

    def _get_href(self, item):
        return item.ident + self.fileext

    def list(self):
        for href, (etag, _item) in self.items.items():
            yield href, etag

    def get(self, href):
        etag, item = self.items[href]
        return item, etag

    def has(self, href):
        return href in self.items

    def upload(self, item):
        href = self._get_href(item)
        if href in self.items:
            raise exceptions.AlreadyExistingError(existing_href=href)
        etag = _random_string()
        self.items[href] = (etag, item)
        return href, etag

    def update(self, href, item, etag):
        if href not in self.items:
            raise exceptions.NotFoundError(href)
        actual_etag, _ = self.items[href]
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        new_etag = _random_string()
        self.items[href] = (new_etag, item)
        return new_etag

    def delete(self, href, etag):
        if not self.has(href):
            raise exceptions.NotFoundError(href)
        if etag != self.items[href][0]:
            raise exceptions.WrongEtagError(etag)
        del self.items[href]

    def get_meta(self, key):
        return normalize_meta_value(self.metadata.get(key))

    def set_meta(self, key, value):
        self.metadata[key] = normalize_meta_value(value)
