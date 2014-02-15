from unittest import TestCase
from vdirsyncer.storage.base import Item
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.sync import sync
import vdirsyncer.exceptions as exceptions

class SyncTests(TestCase):
    def test_basic(self):
        a = MemoryStorage()
        b = MemoryStorage()
        status = {}
        sync(a, b, status)
        assert len(status) == 0
        assert list(a.list_items()) == []
        assert list(b.list_items()) == []

        item = Item('UID:1')
        a.upload(item)
        sync(a, b, status)
        assert list(status) == ['1']
        obj, uid, etag = next(b.get_items(['1']))
        assert obj.raw == item.raw

        item2 = Item('UID:2')
        b.upload(item2)
        b.delete('1')
        sync(a, b, status)
        assert list(status) == ['2']
        assert next(a.list_items())[0] == '2'
        assert next(b.list_items())[0] == '2'
        obj, uid, etag = next(a.get_items(['2']))
        assert obj.raw == item2.raw

        new_item2 = Item('UID:2\nHUEHUEHUE:PRECISELY')
        old_status = status.copy()
        a.update(new_item2, next(a.list_items())[1])
        sync(a, b, status)
        assert status != old_status
        assert list(status) == list(old_status)
        assert next(a.list_items())[0] == '2'
        assert next(b.list_items())[0] == '2'
        obj, uid, etag = next(b.get_items(['2']))
        assert obj.raw == new_item2.raw
