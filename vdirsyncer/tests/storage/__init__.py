# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
__version__ = '0.1.0'

from unittest import TestCase
import os
import tempfile
import shutil
from vdirsyncer.storage.base import Item
from vdirsyncer.storage.filesystem import FilesystemStorage
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.storage.caldav import CaldavStorage
import vdirsyncer.exceptions as exceptions


class StorageTests(object):

    def _create_bogus_item(self, uid):
        return Item(u'''BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//dmfs.org//mimedir.icalendar//EN
BEGIN:VTODO
CREATED:20130721T142233Z
DTSTAMP:20130730T074543Z
LAST-MODIFIED;VALUE=DATE-TIME:20140122T151338Z
SEQUENCE:2
SUMMARY:Book: Kowlani - Tödlicher Staub
UID:{}
END:VTODO
END:VCALENDAR
'''.format(uid))

    def _get_storage(self, **kwargs):
        raise NotImplementedError()

    def test_generic(self):
        items = map(self._create_bogus_item, range(1, 10))
        s = self._get_storage()
        for item in items:
            s.upload(item)
        hrefs = (href for href, etag in s.list())
        for href in hrefs:
            assert s.has(href)
            obj, etag = s.get(href)
            assert 'UID:{}'.format(obj.uid) in obj.raw

    def test_upload_already_existing(self):
        s = self._get_storage()
        item = self._create_bogus_item(1)
        s.upload(item)
        self.assertRaises(exceptions.PreconditionFailed, s.upload, item)

    def test_update_nonexisting(self):
        s = self._get_storage()
        item = self._create_bogus_item(1)
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
