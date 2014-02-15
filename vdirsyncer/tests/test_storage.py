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

class StorageTests(object):
    def _get_storage(self, **kwargs):
        raise NotImplementedError()

    def test_generic_upload(self):
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
        a = set(uid for uid, etag in s.list_items())
        b = set(str(y) for y in range(1, 10))
        assert a == b


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
