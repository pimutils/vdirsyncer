# -*- coding: utf-8 -*-
'''
    tests.storage.test_singlefile
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import pytest

from vdirsyncer.storage.singlefile import SingleFileStorage

from . import StorageTests
from .. import assert_item_equals


class TestSingleFileStorage(StorageTests):

    storage_class = SingleFileStorage
    supports_collections = False

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self._path = str(tmpdir.join('test.txt'))

    @pytest.fixture
    def get_storage_args(self):
        def inner(**kwargs):
            kwargs.update(path=self._path)
            return kwargs
        return inner

    def test_collection_arg(self, tmpdir):
        with pytest.raises(ValueError):
            self.storage_class(str(tmpdir.join('foo.ics')), collection='ha')

    def test_create_arg(self, tmpdir):
        s = self.storage_class(str(tmpdir) + '/foo.ics')
        assert not s.list()

        s.create = False
        with pytest.raises(IOError):
            s.list()

        with pytest.raises(IOError):
            s = self.storage_class(str(tmpdir) + '/foo.ics', create=False)
