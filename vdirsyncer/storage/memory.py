import datetime
from vdirsyncer.storage.base import Item, Storage 
import vdirsyncer.exceptions as exceptions

class MemoryStorage(Storage):
    def __init__(self, **kwargs):
        self.items = {}  # href => (etag, object)
        super(MemoryStorage, self).__init__(**kwargs)

    def _get_href(self, obj):
        return obj.uid + self.fileext

    def list_items(self):
        for href, (etag, obj) in self.items.items():
            yield href, etag

    def get_items(self, hrefs):
        for href in hrefs:
            etag, obj = self.items[href]
            return obj, href, etag

    def item_exists(self, href):
        return href in self.items

    def upload(self, obj):
        href = self._get_href(obj)
        if href in self.items:
            raise exceptions.AlreadyExistingError(obj)
        etag = datetime.datetime.now()
        self.items[href] = (etag, obj)
        return href, etag

    def update(self, obj, etag):
        href = self._get_href(obj)
        if href not in self.items:
            raise exceptions.NotFoundError(obj)
        etag = datetime.datetime.now()
        self.items[href] = (etag, obj)
        return href, etag
