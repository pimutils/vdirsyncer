
# -*- coding: utf-8 -*-
'''
    tests.storage.filesystem
    ~~~~~~~~~~~~~~~~~~~~~~~~

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

    def test_create_is_false(self, tmpdir):
        with pytest.raises(IOError):
            self.storage_class(str(tmpdir), '.txt', collection='lol',
                               create=False)

    def test_is_not_directory(self, tmpdir):
        with pytest.raises(IOError):
            f = tmpdir.join('hue')
            f.write('stub')
            self.storage_class(str(tmpdir), '.txt', collection='hue')

    def test_create_is_true(self, tmpdir):
        self.storage_class(str(tmpdir), '.txt', collection='asd')
        assert tmpdir.listdir() == [tmpdir.join('asd')]
