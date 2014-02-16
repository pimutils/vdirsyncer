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

def empty_storage(x):
    return list(x.list()) == []

class SyncTests(TestCase):
    def test_irrelevant_status(self):
        a = MemoryStorage()
        b = MemoryStorage()
        status = {'1': ('UID:1', 1234)}
        sync(a, b, status)
        assert not status
        assert empty_storage(a)
        assert empty_storage(b)

    def test_missing_status(self):
        a = MemoryStorage()
        b = MemoryStorage()
        status = {}
        item = Item('UID:1')
        a.upload(item)
        b.upload(item)
        sync(a, b, status)
        assert list(status) == ['1']
        assert a.has('1')
        assert b.has('1')

    def test_upload_and_update(self):
        a = MemoryStorage()
        b = MemoryStorage()
        status = {}

        item = Item('UID:1')  # new item 1 in a
        a.upload(item)
        sync(a, b, status)
        assert b.get('1')[0].raw == item.raw

        item = Item('UID:1\nASDF:YES')  # update of item 1 in b
        b.update(item, b.get('1')[1])
        sync(a, b, status)
        assert a.get('1')[0].raw == item.raw

        item2 = Item('UID:2')  # new item 2 in b
        b.upload(item2)
        sync(a, b, status)
        assert a.get('2')[0].raw == item2.raw

        item2 = Item('UID:2\nASDF:YES')  # update of item 2 in a
        a.update(item2, a.get('2')[1])
        sync(a, b, status)
        assert b.get('2')[0].raw == item2.raw

    def test_deletion(self):
        a = MemoryStorage()
        b = MemoryStorage()
        status = {}

        item = Item('UID:1')
        a.upload(item)
        sync(a, b, status)
        b.delete('1', b.get('1')[1])
        sync(a, b, status)
        assert not a.has('1') and not b.has('1')

        a.upload(item)
        sync(a, b, status)
        assert a.has('1') and b.has('1')
        a.delete('1', a.get('1')[1])
        sync(a, b, status)
        assert not a.has('1') and not b.has('1')

    def test_already_synced(self):
        a = MemoryStorage()
        b = MemoryStorage()
        item = Item('UID:1')
        a.upload(item)
        b.upload(item)
        status = {'1': (a.get('1')[1], b.get('1')[1])}
        old_status = dict(status)
        a.update = b.update = a.upload = b.upload = \
            lambda *a, **kw: self.fail('Method shouldn\'t have been called.')
        sync(a, b, status)
        assert status == old_status
        assert a.has('1') and b.has('1')
