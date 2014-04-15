# -*- coding: utf-8 -*-
'''
    tests.test_sync
    ~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import pytest
from vdirsyncer.storage.base import Item
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.sync import sync
from . import assert_item_equals, normalize_item
import vdirsyncer.exceptions as exceptions


def empty_storage(x):
    return list(x.list()) == []


def test_irrelevant_status():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {'1': ('1.txt', 1234, '1.ics', 2345)}
    sync(a, b, status)
    assert not status
    assert empty_storage(a)
    assert empty_storage(b)


def test_missing_status():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    item = Item(u'UID:1')
    a.upload(item)
    b.upload(item)
    sync(a, b, status)
    assert len(status) == 1
    assert a.has('1.txt')
    assert b.has('1.txt')


def test_missing_status_and_different_items():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    item1 = Item(u'UID:1\nhaha')
    item2 = Item(u'UID:1\nhoho')
    a.upload(item1)
    b.upload(item2)
    with pytest.raises(exceptions.SyncConflict):
        sync(a, b, status)
    assert not status
    sync(a, b, status, conflict_resolution='a wins')
    assert_item_equals(item1, b.get('1.txt')[0])
    assert_item_equals(item1, a.get('1.txt')[0])


def test_upload_and_update():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}

    item = Item(u'UID:1')  # new item 1 in a
    a.upload(item)
    sync(a, b, status)
    assert_item_equals(b.get('1.txt')[0], item)

    item = Item(u'UID:1\nASDF:YES')  # update of item 1 in b
    b.update('1.txt', item, b.get('1.txt')[1])
    sync(a, b, status)
    assert_item_equals(a.get('1.txt')[0], item)

    item2 = Item(u'UID:2')  # new item 2 in b
    b.upload(item2)
    sync(a, b, status)
    assert_item_equals(a.get('2.txt')[0], item2)

    item2 = Item(u'UID:2\nASDF:YES')  # update of item 2 in a
    a.update('2.txt', item2, a.get('2.txt')[1])
    sync(a, b, status)
    assert_item_equals(b.get('2.txt')[0], item2)


def test_deletion():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}

    item = Item(u'UID:1')
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


def test_already_synced():
    a = MemoryStorage()
    b = MemoryStorage()
    item = Item(u'UID:1')
    a.upload(item)
    b.upload(item)
    status = {
        '1': ('1.txt', a.get('1.txt')[1], '1.txt', b.get('1.txt')[1])
    }
    old_status = dict(status)
    a.update = b.update = a.upload = b.upload = \
        lambda *a, **kw: pytest.fail('Method shouldn\'t have been called.')

    for i in (1, 2):
        sync(a, b, status)
        assert status == old_status
        assert a.has('1.txt') and b.has('1.txt')


@pytest.mark.parametrize('winning_storage', 'ab')
def test_conflict_resolution_both_etags_new(winning_storage):
    a = MemoryStorage()
    b = MemoryStorage()
    item = Item(u'UID:1')
    href_a, etag_a = a.upload(item)
    href_b, etag_b = b.upload(item)
    status = {}
    sync(a, b, status)
    assert status
    a.update(href_a, Item(u'UID:1\nitem a'), etag_a)
    b.update(href_b, Item(u'UID:1\nitem b'), etag_b)
    with pytest.raises(exceptions.SyncConflict):
        sync(a, b, status)
    sync(a, b, status, conflict_resolution='{} wins'.format(winning_storage))
    item_a, _ = a.get(href_a)
    item_b, _ = b.get(href_b)
    assert_item_equals(item_a, item_b)
    n = normalize_item(item_a)
    assert u'UID:1' in n
    assert u'item {}'.format(winning_storage) in n


def test_conflict_resolution_invalid_mode():
    a = MemoryStorage()
    b = MemoryStorage()
    item_a = Item(u'UID:1\nitem a')
    item_b = Item(u'UID:1\nitem b')
    a.upload(item_a)
    b.upload(item_b)
    with pytest.raises(ValueError):
        sync(a, b, {}, conflict_resolution='yolo')


def test_conflict_resolution_new_etags_without_changes():
    a = MemoryStorage()
    b = MemoryStorage()
    item = Item(u'UID:1')
    href_a, etag_a = a.upload(item)
    href_b, etag_b = b.upload(item)
    status = {'1': (href_a, 'BOGUS_a', href_b, 'BOGUS_b')}
    sync(a, b, status)
    assert status == {'1': (href_a, etag_a, href_b, etag_b)}


def test_uses_get_multi(monkeypatch):
    def breakdown(*a, **kw):
        raise AssertionError('Expected use of get_multi')

    get_multi_calls = []

    old_get = MemoryStorage.get

    def get_multi(self, hrefs):
        get_multi_calls.append(hrefs)
        for href in hrefs:
            item, etag = old_get(self, href)
            yield href, item, etag

    monkeypatch.setattr(MemoryStorage, 'get', breakdown)
    monkeypatch.setattr(MemoryStorage, 'get_multi', get_multi)

    a = MemoryStorage()
    b = MemoryStorage()
    item = Item(u'UID:1')
    expected_href, etag = a.upload(item)

    sync(a, b, {})
    assert get_multi_calls == [[expected_href]]
