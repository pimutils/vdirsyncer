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
        status = {'1': ('1.txt', 1234, '1.ics', 2345)}
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
        assert len(status) == 1
        assert a.has('1.txt')
        assert b.has('1.txt')

    def test_missing_status_and_different_items(self):
        return  # TODO
        a = MemoryStorage()
        b = MemoryStorage()
        status = {}
        item1 = Item('UID:1\nhaha')
        item2 = Item('UID:1\nhoho')
        a.upload(item1)
        b.upload(item2)
        sync(a, b, status)
        assert status
        assert a.get('1.txt')[0].raw == b.get('1.txt')[0].raw

    def test_upload_and_update(self):
        a = MemoryStorage()
        b = MemoryStorage()
        status = {}

        item = Item('UID:1')  # new item 1 in a
        a.upload(item)
        sync(a, b, status)
        assert b.get('1.txt')[0].raw == item.raw

        item = Item('UID:1\nASDF:YES')  # update of item 1 in b
        b.update('1.txt', item, b.get('1.txt')[1])
        sync(a, b, status)
        assert a.get('1.txt')[0].raw == item.raw

        item2 = Item('UID:2')  # new item 2 in b
        b.upload(item2)
        sync(a, b, status)
        assert a.get('2.txt')[0].raw == item2.raw

        item2 = Item('UID:2\nASDF:YES')  # update of item 2 in a
        a.update('2.txt', item2, a.get('2.txt')[1])
        sync(a, b, status)
        assert b.get('2.txt')[0].raw == item2.raw

    def test_deletion(self):
        a = MemoryStorage()
        b = MemoryStorage()
        status = {}

        item = Item('UID:1')
        a.upload(item)
        sync(a, b, status)
        b.delete('1.txt', b.get('1.txt')[1])
        sync(a, b, status)
        assert not a.has('1.txt') and not b.has('1.txt')

        a.upload(item)
        sync(a, b, status)
        assert a.has('1.txt') and b.has('1.txt')
        a.delete('1.txt', a.get('1.txt')[1])
        sync(a, b, status)
        assert not a.has('1.txt') and not b.has('1.txt')

    def test_already_synced(self):
        a = MemoryStorage()
        b = MemoryStorage()
        item = Item('UID:1')
        a.upload(item)
        b.upload(item)
        status = {
            '1': ('1.txt', a.get('1.txt')[1], '1.txt', b.get('1.txt')[1])
        }
        old_status = dict(status)
        a.update = b.update = a.upload = b.upload = \
            lambda *a, **kw: self.fail('Method shouldn\'t have been called.')
        sync(a, b, status)
        assert status == old_status
        assert a.has('1.txt') and b.has('1.txt')
