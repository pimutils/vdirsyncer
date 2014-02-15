import datetime
from vdirsyncer.storage.base import Item, Storage 
import vdirsyncer.exceptions as exceptions

class MemoryStorage(Storage):
    def __init__(self, **kwargs):
        self.items = {}  # uid => (etag, object)
        super(MemoryStorage, self).__init__(**kwargs)

    def list_items(self):
        for uid, (etag, obj) in self.items.items():
            yield uid, etag

    def get_items(self, uids):
        for uid in uids:
            etag, obj = self.items[uid]
            return obj, uid, etag

    def item_exists(self, uid):
        return uid in self.items

    def upload(self, obj):
        if obj.uid in self.items:
            raise exceptions.AlreadyExistingError(obj)
        etag = datetime.datetime.now()
        self.items[obj.uid] = (etag, obj)
        return obj.uid, etag

    def update(self, obj, etag):
        if obj.uid not in self.items:
            raise exceptions.NotFoundError(obj)
        etag = datetime.datetime.now()
        self.items[obj.uid] = (etag, obj)
        return obj.uid, etag
