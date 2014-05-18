# -*- coding: utf-8 -*-
'''
    tests.storage
    ~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
import random

import pytest

from .. import assert_item_equals, SIMPLE_TEMPLATE
import vdirsyncer.exceptions as exceptions
from vdirsyncer.storage.base import Item
from vdirsyncer.utils import text_type, iteritems


class StorageTests(object):
    item_template = SIMPLE_TEMPLATE

    def _create_bogus_item(self, item_template=None):
        r = random.random()
        item_template = item_template or self.item_template
        return Item(item_template.format(r=r))

    def get_storage_args(self, collection=None):
        raise NotImplementedError()

    def _get_storage(self):
        s = self.storage_class(**self.get_storage_args())
        assert not list(s.list())
        return s

    def test_generic(self):
        items = [self._create_bogus_item() for i in range(1, 10)]
        s = self._get_storage()
        hrefs = []
        for item in items:
            hrefs.append(s.upload(item))
        hrefs.sort()
        assert hrefs == sorted(s.list())
        for href, etag in hrefs:
            assert isinstance(href, (text_type, bytes))
            assert isinstance(etag, (text_type, bytes))
            assert s.has(href)
            item, etag2 = s.get(href)
            assert etag == etag2

    def test_empty_get_multi(self):
        s = self._get_storage()
        assert list(s.get_multi([])) == []

    def test_upload_already_existing(self):
        s = self._get_storage()
        item = self._create_bogus_item()
        s.upload(item)
        with pytest.raises(exceptions.PreconditionFailed):
            s.upload(item)

    def test_upload(self):
        s = self._get_storage()
        item = self._create_bogus_item()
        href, etag = s.upload(item)
        assert_item_equals(s.get(href)[0], item)

    def test_update(self):
        s = self._get_storage()
        item = self._create_bogus_item()
        href, etag = s.upload(item)
        assert_item_equals(s.get(href)[0], item)

        new_item = self._create_bogus_item()
        new_etag = s.update(href, new_item, etag)
        # See https://github.com/untitaker/vdirsyncer/issues/48
        assert isinstance(new_etag, (bytes, text_type))
        assert_item_equals(s.get(href)[0], new_item)

    def test_update_nonexisting(self):
        s = self._get_storage()
        item = self._create_bogus_item()
        with pytest.raises(exceptions.PreconditionFailed):
            s.update(s._get_href(item), item, '"123"')
        with pytest.raises(exceptions.PreconditionFailed):
            s.update('huehue', item, '"123"')

    def test_wrong_etag(self):
        s = self._get_storage()
        item = self._create_bogus_item()
        href, etag = s.upload(item)
        with pytest.raises(exceptions.PreconditionFailed):
            s.update(href, item, '"lolnope"')
        with pytest.raises(exceptions.PreconditionFailed):
            s.delete(href, '"lolnope"')

    def test_delete(self):
        s = self._get_storage()
        href, etag = s.upload(self._create_bogus_item())
        s.delete(href, etag)
        assert not list(s.list())

    def test_delete_nonexisting(self):
        s = self._get_storage()
        with pytest.raises(exceptions.PreconditionFailed):
            s.delete('1', '"123"')

    def test_list(self):
        s = self._get_storage()
        assert not list(s.list())
        s.upload(self._create_bogus_item())
        assert list(s.list())

    def test_discover(self):
        collections = set()

        def main():
            for i in range(1, 5):
                collection = 'test{}'.format(i)
                # Create collections on-the-fly for most storages
                # Except ownCloud, which already has all of them, and more
                i += 1
                s = self.storage_class(
                    **self.get_storage_args(collection=collection))

                # radicale ignores empty collections during discovery
                item = self._create_bogus_item()
                s.upload(item)

                collections.add(s.collection)
        main()  # remove leftover variables from loop for safety

        d = self.storage_class.discover(
            **self.get_storage_args(collection=None))

        def main():
            for s in d:
                if s.collection not in collections:
                    # ownCloud has many more collections, as on-the-fly
                    # creation doesn't really work there. Skip those
                    # collections, as they are not relevant to us.
                    print('Skipping {}'.format(s.collection))
                    continue
                collections.remove(s.collection)
        main()

        assert not collections

    def test_discover_collection_arg(self):
        args = self.get_storage_args(collection='test2')
        with pytest.raises(TypeError) as excinfo:
            list(self.storage_class.discover(**args))

        assert 'collection argument must not be given' in str(excinfo.value)

    def test_collection_arg(self):
        s = self.storage_class(**self.get_storage_args(collection='test2'))
        # Can't do stronger assertion because of radicale, which needs a
        # fileextension to guess the collection type.
        assert 'test2' in s.collection

    def test_has(self):
        s = self._get_storage()
        assert not s.has('asd')
        href, etag = s.upload(self._create_bogus_item())
        assert s.has(href)
        assert not s.has('asd')

    def test_update_others_stay_the_same(self):
        s = self._get_storage()
        info = dict([
            s.upload(self._create_bogus_item()),
            s.upload(self._create_bogus_item()),
            s.upload(self._create_bogus_item()),
            s.upload(self._create_bogus_item())
        ])

        assert dict(
            (href, etag) for href, item, etag
            in s.get_multi(href for href, etag in iteritems(info))
        ) == info
