
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.test_memory
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
__version__ = '0.1.0'

from unittest import TestCase
from vdirsyncer.storage.memory import MemoryStorage
from . import StorageTests


class MemoryStorageTests(TestCase, StorageTests):

    def _get_storage(self, **kwargs):
        return MemoryStorage(**kwargs)
