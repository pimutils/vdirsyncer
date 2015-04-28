# -*- coding: utf-8 -*-

import pytest

from vdirsyncer.storage.singlefile import SingleFileStorage

from . import StorageTests


class TestSingleFileStorage(StorageTests):

    storage_class = SingleFileStorage
    supports_collections = False
    supports_metadata = False

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self._path = str(tmpdir.ensure('test.txt'))

    @pytest.fixture
    def get_storage_args(self):
        def inner(**kwargs):
            kwargs.update(path=self._path)
            return kwargs
        return inner

    def test_collection_arg(self, tmpdir):
        with pytest.raises(ValueError):
            self.storage_class(str(tmpdir.join('foo.ics')), collection='ha')
