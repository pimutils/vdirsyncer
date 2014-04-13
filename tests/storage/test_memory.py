
# -*- coding: utf-8 -*-
'''
    tests.storage.test_memory
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from vdirsyncer.storage.memory import MemoryStorage
from . import StorageTests


class TestMemoryStorage(StorageTests):

    storage_class = MemoryStorage

    def get_storage_args(self, **kwargs):
        return kwargs

    def test_discover(self):
        '''This test doesn't make any sense here.'''

    def test_discover_collection_arg(self):
        '''This test doesn't make any sense here.'''

    def test_collection_arg(self):
        '''This test doesn't make any sense here.'''
