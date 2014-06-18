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
from .. import EVENT_TEMPLATE, assert_item_equals


class TestSingleFileStorage(StorageTests):

    storage_class = SingleFileStorage
    item_template = EVENT_TEMPLATE

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self._path = str(tmpdir.join('test.txt'))

    def get_storage_args(self, **kwargs):
        return dict(path=self._path)

    def test_discover(self):
        '''This test doesn't make any sense here.'''

    def test_discover_collection_arg(self):
        '''This test doesn't make any sense here.'''

    def test_collection_arg(self):
        '''This test doesn't make any sense here.'''

    def test_update(self):
        '''The original testcase tries to fetch with the old href. But this
        storage doesn't have real hrefs, so the href might change if the
        underlying UID changes. '''

        s = self._get_storage()
        item = self._create_bogus_item()
        href, etag = s.upload(item)
        assert_item_equals(s.get(href)[0], item)

        new_item = self._create_bogus_item()
        s.update(href, new_item, etag)
        ((new_href, new_etag),) = s.list()
        assert_item_equals(s.get(new_href)[0], new_item)
