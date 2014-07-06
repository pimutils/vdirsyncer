
# -*- coding: utf-8 -*-
'''
    tests.storage.test_memory
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

from vdirsyncer.storage.memory import MemoryStorage

from . import BaseStorageTests


class TestMemoryStorage(BaseStorageTests):

    storage_class = MemoryStorage

    def get_storage_args(self, **kwargs):
        return kwargs
