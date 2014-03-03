# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from vdirsyncer.storage.base import Item
import vdirsyncer.exceptions as exceptions


class StorageTests(object):

    def _create_bogus_item(self, uid):
        return Item(u'UID:{}'.format(uid))

    def _get_storage(self, **kwargs):
        raise NotImplementedError()

    def test_generic(self):
        items = map(self._create_bogus_item, range(1, 10))
        for i, item in enumerate(items):
            assert item.uid == unicode(i + 1), item.raw
        s = self._get_storage()
        hrefs = []
        for item in items:
            hrefs.append(s.upload(item))
        hrefs.sort()
        assert hrefs == sorted(s.list())
        for href, etag in hrefs:
            assert s.has(href)
            obj, etag2 = s.get(href)
            assert etag == etag2
            assert 'UID:{}'.format(obj.uid) in obj.raw

    def test_upload_already_existing(self):
        s = self._get_storage()
        item = self._create_bogus_item(1)
        s.upload(item)
        self.assertRaises(exceptions.PreconditionFailed, s.upload, item)

    def test_update(self):
        s = self._get_storage()
        item = self._create_bogus_item(1)
        href, etag = s.upload(item)
        assert s.get(href)[0].raw == item.raw
        new_item = Item(item.raw + u'\nX-SOMETHING: YES\n')
        s.update(href, new_item, etag)
        assert s.get(href)[0].raw == new_item.raw

    def test_update_nonexisting(self):
        s = self._get_storage()
        item = self._create_bogus_item(1)
        self.assertRaises(
            exceptions.PreconditionFailed, s.update, s._get_href('1'), item, 123)
        self.assertRaises(
            exceptions.PreconditionFailed, s.update, 'huehue', item, 123)

    def test_wrong_etag(self):
        s = self._get_storage()
        obj = self._create_bogus_item(1)
        href, etag = s.upload(obj)
        self.assertRaises(
            exceptions.PreconditionFailed, s.update, href, obj, 'lolnope')
        self.assertRaises(
            exceptions.PreconditionFailed, s.delete, href, 'lolnope')

    def test_delete_nonexisting(self):
        s = self._get_storage()
        self.assertRaises(exceptions.PreconditionFailed, s.delete, '1', 123)

    def test_list(self):
        s = self._get_storage()
        assert not list(s.list())
        s.upload(self._create_bogus_item('1'))
        assert list(s.list())
