
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.filesystem
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from unittest import TestCase
import pytest
import os
from vdirsyncer.storage.filesystem import FilesystemStorage
from . import StorageTests


@pytest.mark.usefixtures('class_tmpdir')
class FilesystemStorageTests(TestCase, StorageTests):
    storage_class = FilesystemStorage

    def get_storage_args(self, collection=None):
        path = self.tmpdir
        if collection is not None:
            path = os.path.join(path, collection)
            os.makedirs(path)
        return {'path': path, 'fileext': '.txt'}
