
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.filesystem
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

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

    def teardown_method(self, method):
        if self.tmpdir is not None:
            shutil.rmtree(self.tmpdir)
            self.tmpdir = None
