
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.filesystem
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
__version__ = '0.1.0'

from unittest import TestCase
import tempfile
import shutil
from vdirsyncer.storage.filesystem import FilesystemStorage
from . import StorageTests


class FilesystemStorageTests(TestCase, StorageTests):
    tmpdir = None

    def _get_storage(self, **kwargs):
        path = self.tmpdir = tempfile.mkdtemp()
        return FilesystemStorage(path=path, fileext='.txt', **kwargs)

    def tearDown(self):
        if self.tmpdir is not None:
            shutil.rmtree(self.tmpdir)
            self.tmpdir = None
