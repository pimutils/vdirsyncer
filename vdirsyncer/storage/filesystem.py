import os
from vdirsyncer.storage.base import Storage, Item
import vdirsyncer.exceptions as exceptions

class FilesystemStorage(Storage):
    def __init__(self, path, **kwargs):
        self.path = path
        super(FilesystemStorage, self).__init__(**kwargs)

    def _get_etag(self, href):
        return os.path.getmtime(href)

    def _get_href(self, obj):
        return os.path.join(self.path, obj.uid + self.fileext)

    def _get_hrefs(self):
        for fname in os.listdir(self.path):
            href = os.path.join(self.path, fname)
            if os.path.isfile(href):
                yield href

    def list_items(self):
        for href in self._get_hrefs():
            yield href, self._get_etag(href)

    def get_items(self, hrefs):
        for href in hrefs:
            with open(href, 'rb') as f:
                yield Item(f.read()), href, self._get_etag(href)

    def item_exists(self, href):
        return os.path.isfile(path)

    def upload(self, obj):
        href = self._get_href(obj)
        if os.path.exists(href):
            raise exceptions.AlreadyExistingError(href)
        with open(href, 'wb+') as f:
            f.write(obj.raw)
        return href, self._get_etag(href)

    def update(self, obj, etag):
        href = self._get_href(obj)
        actual_etag = self._get_etag(href)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)
        if not os.path.exists(href):
            raise exceptions.NotFoundError(href)
        with open(href, 'wb') as f:
            f.write(obj.raw)

        return self._get_etag(href)
