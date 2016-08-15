# -*- coding: utf-8 -*-

import pytest

from vdirsyncer.storage.singlefile import SingleFileStorage

from . import StorageTests


class TestSingleFileStorage(StorageTests):

    storage_class = SingleFileStorage
    supports_metadata = False

    @pytest.fixture
    def get_storage_args(self, tmpdir):
        def inner(collection='test'):
            rv = {'path': str(tmpdir.join('%s.txt')),
                  'collection': collection}
            if collection is not None:
                rv = self.storage_class.create_collection(**rv)
            return rv
        return inner
