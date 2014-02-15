import os
from vdirsyncer.storage.base import Storage, Item
import vdirsyncer.exceptions as exceptions

class FilesystemStorage(Storage):
    def __init__(self, path, **kwargs):
        self.path = path
        super(FilesystemStorage, self).__init__(**kwargs)

    def _get_filepath(self, uid):
        return os.path.join(self.path, uid + self.fileext)

    def list_items(self):
        for fname in os.listdir(self.path):
            fpath = os.path.join(self.path, fname)
            if os.path.isfile(fpath) and fname.endswith(self.fileext):
                uid = fname[:-len(self.fileext)]
                yield uid, os.path.getmtime(fpath)

    def get_items(self, uids):
        for uid in uids:
            fpath = self._get_filepath(uid)
            with open(fpath, 'rb') as f:
                yield Item(f.read()), uid, os.path.getmtime(fpath)

    def item_exists(self, uid):
        return os.path.isfile(self._get_filepath(uid))

    def upload(self, obj):
        fpath = self._get_filepath(obj.uid)
        if os.path.exists(fpath):
            raise exceptions.AlreadyExistingError(obj.uid)
        with open(fpath, 'wb+') as f:
            f.write(obj.raw)
        return obj.uid, os.path.getmtime(fpath)

    def update(self, obj, etag):
        fpath = self._get_filepath(obj)
        if not os.path.exists(fpath):
            raise exceptions.NotFoundError(href)
        actual_etag = os.path.getmtime(fpath)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)
        with open(fpath, 'wb') as f:
            f.write(obj.raw)
        return os.path.getmtime(fpath)
