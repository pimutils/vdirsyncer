# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.test_sync
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from unittest import TestCase
from vdirsyncer.storage.base import Item
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.sync import sync
import vdirsyncer.exceptions as exceptions

def only(x):
    x = list(x)
    assert len(x) == 1, x
    return x[0]

def empty_storage(x):
    return list(x.list()) == []

class SyncTests(TestCase):
    def test_basic(self):
        a = MemoryStorage()
        b = MemoryStorage()
        status = {}
        sync(a, b, status)
        assert not status
        assert empty_storage(a)
        assert empty_storage(b)

        # creation
        item = Item('UID:1')
        a.upload(item)
        sync(a, b, status)
        obj_a, uid_a, etag_a = a.get('1')
        obj_b, uid_b, etag_b = b.get('1')
        assert obj_a.raw == obj_b.raw == item.raw
        assert uid_a == uid_b == only(status) == '1'

        # creation and deletion
        item2 = Item('UID:2')
        b.upload(item2)
        b.delete('1', etag_b)
        sync(a, b, status)
        assert list(status) == ['2']
        assert next(a.list())[0] == '2'
        assert next(b.list())[0] == '2'
        obj2_a, uid2_a, etag2_a = a.get('2')
        assert obj2_a.raw == item2.raw

        new_item2 = Item('UID:2\nHUEHUEHUE:PRECISELY')
        old_status = status.copy()
        a.update(new_item2, next(a.list())[1])
        sync(a, b, status)
        assert status != old_status
        assert list(status) == list(old_status)
        assert next(a.list())[0] == '2'
        assert next(b.list())[0] == '2'
        obj, uid, etag = b.get('2')
        assert obj.raw == new_item2.raw
