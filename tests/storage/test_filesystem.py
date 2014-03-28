
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.filesystem
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import pytest
import os
from vdirsyncer.storage.filesystem import FilesystemStorage
from . import StorageTests


class TestFilesystemStorage(StorageTests):
    storage_class = FilesystemStorage

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self.tmpdir = str(tmpdir)

    def get_storage_args(self, collection=None):
        path = self.tmpdir
        if collection is not None:
            os.makedirs(os.path.join(path, collection))
        return {'path': path, 'fileext': '.txt', 'collection': collection}
