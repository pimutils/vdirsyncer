
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

    def _get_storage(self, **kwargs):
        return FilesystemStorage(path=self.tmpdir, fileext='.txt', **kwargs)

    def test_discover(self):
        paths = set()
        for i, collection in enumerate('abcd'):
            p = os.path.join(self.tmpdir, collection)
            os.makedirs(os.path.join(self.tmpdir, collection))
            fname = os.path.join(p, 'asdf.txt')
            with open(fname, 'w+') as f:
                f.write(self._create_bogus_item(i).raw)
            paths.add(p)

        storages = list(FilesystemStorage.discover(path=self.tmpdir,
                                                   fileext='.txt'))
        assert len(storages) == 4
        for s in storages:
            assert s.path in paths
