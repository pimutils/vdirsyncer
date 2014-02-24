# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.test_storage
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
import vdirsyncer.exceptions as exceptions

class StorageTests(object):
    def _get_storage(self, **kwargs):
        raise NotImplementedError()

    def test_generic(self):
        items = [
            'UID:1',
            'UID:2',
            'UID:3',
            'UID:4',
            'UID:5',
            'UID:6',
            'UID:7',
            'UID:8',
            'UID:9'
        ]
        fileext = '.lol'
        s = self._get_storage(fileext=fileext)
        for item in items:
            s.upload(Item(item))
        hrefs = (href for href, etag in s.list())
        for href in hrefs:
            assert s.has(href)
            obj, etag = s.get(href)
            assert obj.raw == 'UID:{}'.format(obj.uid)

    def test_upload_already_existing(self):
        s = self._get_storage()
        item = Item('UID:1')
        s.upload(item)
        self.assertRaises(exceptions.AlreadyExistingError, s.upload, item)

    def test_update_nonexisting(self):
        s = self._get_storage()
        item = Item('UID:1')
        self.assertRaises(exceptions.NotFoundError, s.update, 'huehue', item, 123)

    def test_wrong_etag(self):
        s = self._get_storage()
        obj = Item('UID:1')
        href, etag = s.upload(obj)
        self.assertRaises(exceptions.WrongEtagError, s.update, href, obj, 'lolnope')
        self.assertRaises(exceptions.WrongEtagError, s.delete, href, 'lolnope')

    def test_delete_nonexisting(self):
        s = self._get_storage()
        self.assertRaises(exceptions.NotFoundError, s.delete, '1', 123)


class FilesystemStorageTests(TestCase, StorageTests):
    tmpdir = None
    def _get_storage(self, **kwargs):
        path = self.tmpdir = tempfile.mkdtemp()
        return FilesystemStorage(path=path, **kwargs)

    def tearDown(self):
        if self.tmpdir is not None:
            shutil.rmtree(self.tmpdir)
            self.tmpdir = None

class MemoryStorageTests(TestCase, StorageTests):
    def _get_storage(self, **kwargs):
        return MemoryStorage(**kwargs)
