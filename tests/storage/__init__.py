# -*- coding: utf-8 -*-
'''
    tests.storage
    ~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''
import random

import pytest

import vdirsyncer.exceptions as exceptions
from vdirsyncer.storage.base import Item
from vdirsyncer.utils.compat import iteritems, text_type

from .. import EVENT_TEMPLATE, TASK_TEMPLATE, VCARD_TEMPLATE, \
    assert_item_equals


def format_item(item_template):
    # assert that special chars are handled correctly.
    r = '{}@vdirsyncer'.format(random.random())
    return Item(item_template.format(r=r))


class BaseStorageTests(object):
    @pytest.fixture
    def get_storage_args(self):
        '''
        Return a function with the following properties:

        :param collection: The collection name to use.
        '''
        raise NotImplementedError()

    @pytest.fixture
    def s(self, get_storage_args):
        return self.storage_class(**get_storage_args())

    @pytest.fixture(params=[EVENT_TEMPLATE, TASK_TEMPLATE, VCARD_TEMPLATE])
    def item_template(self, request):
        return request.param

    @pytest.fixture
    def get_item(self, item_template):
        return lambda: format_item(item_template)

    def test_generic(self, s, get_item):
        items = [get_item() for i in range(1, 10)]
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

    def test_empty_get_multi(self, s):
        assert list(s.get_multi([])) == []

    def test_get_multi_duplicates(self, s, get_item):
        href, etag = s.upload(get_item())
        (href2, item, etag2), = s.get_multi([href] * 2)
        assert href2 == href
        assert etag2 == etag

    def test_upload_already_existing(self, s, get_item):
        item = get_item()
        s.upload(item)
        with pytest.raises(exceptions.PreconditionFailed):
            s.upload(item)

    def test_upload(self, s, get_item):
        item = get_item()
        href, etag = s.upload(item)
        assert_item_equals(s.get(href)[0], item)

    def test_update(self, s, get_item):
        item = get_item()
        href, etag = s.upload(item)
        assert_item_equals(s.get(href)[0], item)

        new_item = get_item()
        new_etag = s.update(href, new_item, etag)
        # See https://github.com/untitaker/vdirsyncer/issues/48
        assert isinstance(new_etag, (bytes, text_type))
        assert_item_equals(s.get(href)[0], new_item)

    def test_update_nonexisting(self, s, get_item):
        item = get_item()
        with pytest.raises(exceptions.PreconditionFailed):
            s.update('huehue', item, '"123"')

    def test_wrong_etag(self, s, get_item):
        item = get_item()
        href, etag = s.upload(item)
        with pytest.raises(exceptions.PreconditionFailed):
            s.update(href, item, '"lolnope"')
        with pytest.raises(exceptions.PreconditionFailed):
            s.delete(href, '"lolnope"')

    def test_delete(self, s, get_item):
        href, etag = s.upload(get_item())
        s.delete(href, etag)
        assert not list(s.list())

    def test_delete_nonexisting(self, s, get_item):
        with pytest.raises(exceptions.PreconditionFailed):
            s.delete('1', '"123"')

    def test_list(self, s, get_item):
        assert not list(s.list())
        href, etag = s.upload(get_item())
        assert list(s.list()) == [(href, etag)]

    def test_has(self, s, get_item):
        assert not s.has('asd')
        href, etag = s.upload(get_item())
        assert s.has(href)
        assert not s.has('asd')
        s.delete(href, etag)
        assert not s.has(href)

    def test_update_others_stay_the_same(self, s, get_item):
        info = dict([
            s.upload(get_item()),
            s.upload(get_item()),
            s.upload(get_item()),
            s.upload(get_item())
        ])

        assert dict(
            (href, etag) for href, item, etag
            in s.get_multi(href for href, etag in iteritems(info))
        ) == info

    def test_repr(self, s, get_storage_args):
        assert self.storage_class.__name__ in repr(s)
        assert s.instance_name is None


class SupportsCollections(object):

    def test_discover(self, get_storage_args, get_item):
        expected = set()

        for i in range(1, 5):
            # Create collections, but use the "collection" attribute because
            # Radicale requires file extensions in their names.
            expected.add(
                self.storage_class(
                    **get_storage_args(collection='test{}'.format(i))
                ).collection
            )

        d = self.storage_class.discover(
            **get_storage_args(collection=None))

        actual = set(s.collection for s in d)
        assert actual >= expected

    def test_discover_collection_arg(self, get_storage_args):
        args = get_storage_args(collection='test2')
        with pytest.raises(TypeError) as excinfo:
            list(self.storage_class.discover(**args))

        assert 'collection argument must not be given' in str(excinfo.value)

    def test_collection_arg(self, get_storage_args):
        s = self.storage_class(**get_storage_args(collection='test2'))
        # Can't do stronger assertion because of radicale, which needs a
        # fileextension to guess the collection type.
        assert 'test2' in s.collection


class StorageTests(BaseStorageTests, SupportsCollections):
    pass
