# -*- coding: utf-8 -*-

import random

import pytest

import vdirsyncer.exceptions as exceptions
from vdirsyncer.storage.base import Item
from vdirsyncer.utils.compat import iteritems, text_type, urlquote, urlunquote

from .. import EVENT_TEMPLATE, TASK_TEMPLATE, VCARD_TEMPLATE, \
    assert_item_equals


def get_server_mixin(server_name):
    from . import __name__ as base
    x = __import__('{}.servers.{}'.format(base, server_name), fromlist=[''])
    return x.ServerMixin


def format_item(item_template, uid=None):
    # assert that special chars are handled correctly.
    r = random.random()
    return Item(item_template.format(r=r, uid=uid or r))


class StorageTests(object):
    storage_class = None
    supports_collections = True
    supports_metadata = True

    @pytest.fixture(params=['VEVENT', 'VTODO', 'VCARD'])
    def item_type(self, request):
        '''Parametrize with all supported item types.'''
        return request.param

    @pytest.fixture
    def get_storage_args(self):
        '''
        Return a function with the following properties:

        :param collection: The name of the collection to create and use.
        '''
        raise NotImplementedError()

    @pytest.fixture
    def s(self, get_storage_args):
        return self.storage_class(**get_storage_args())

    @pytest.fixture
    def get_item(self, item_type):
        template = {
            'VEVENT': EVENT_TEMPLATE,
            'VTODO': TASK_TEMPLATE,
            'VCARD': VCARD_TEMPLATE,
        }[item_type]

        return lambda **kw: format_item(template, **kw)

    @pytest.fixture
    def requires_collections(self):
        if not self.supports_collections:
            pytest.skip('This storage does not support collections.')

    @pytest.fixture
    def requires_metadata(self):
        if not self.supports_metadata:
            pytest.skip('This storage does not support metadata.')

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
        if getattr(self, 'dav_server', '') == 'baikal':
            # https://github.com/untitaker/vdirsyncer/issues/160
            pytest.xfail(reason='Baikal uses an old version of SabreDAV.')

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

        new_item = get_item(uid=item.uid)
        new_etag = s.update(href, new_item, etag)
        # See https://github.com/untitaker/vdirsyncer/issues/48
        assert isinstance(new_etag, (bytes, text_type))
        assert_item_equals(s.get(href)[0], new_item)

    def test_update_nonexisting(self, s, get_item):
        if getattr(self, 'dav_server', '') == 'baikal':
            # https://github.com/untitaker/vdirsyncer/issues/160
            pytest.xfail(reason='Baikal uses an old version of SabreDAV.')

        item = get_item()
        with pytest.raises(exceptions.PreconditionFailed):
            s.update('huehue', item, '"123"')

    def test_wrong_etag(self, s, get_item):
        if getattr(self, 'dav_server', '') == 'baikal':
            # https://github.com/untitaker/vdirsyncer/issues/160
            pytest.xfail(reason='Baikal uses an old version of SabreDAV.')

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
        if getattr(self, 'dav_server', '') == 'owncloud':
            # https://github.com/owncloud/calendar/issues/935
            pytest.skip('ownCloud is buggy.')
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

    def test_discover(self, requires_collections, get_storage_args, get_item):
        expected = set()
        items = {}

        for i in range(1, 5):
            # Create collections, but use the "collection" attribute because
            # Radicale requires file extensions in their names.
            collection = 'test{}'.format(i)
            s = self.storage_class(
                **self.storage_class.create_collection(
                    **get_storage_args(collection=collection)
                )
            )

            items[s.collection] = [s.upload(get_item())]
            expected.add(s.collection)

        d = self.storage_class.discover(
            **get_storage_args(collection=None))

        actual = set(args['collection'] for args in d)
        assert actual >= expected

        for storage_args in d:
            collection = storage_args['collection']
            if collection not in expected:
                continue
            s = self.storage_class(**storage_args)
            rv = list(s.list())
            assert rv == items[collection]

    def test_discover_collection_arg(self, requires_collections,
                                     get_storage_args):
        args = get_storage_args(collection='test2')
        with pytest.raises(TypeError) as excinfo:
            list(self.storage_class.discover(**args))

        assert 'collection argument must not be given' in str(excinfo.value)

    def test_collection_arg(self, requires_collections, get_storage_args):
        s = self.storage_class(**get_storage_args(collection='test2'))
        # Can't do stronger assertion because of radicale, which needs a
        # fileextension to guess the collection type.
        assert 'test2' in s.collection

    def test_case_sensitive_uids(self, s, get_item):
        s.upload(get_item(uid='A' * 42))
        s.upload(get_item(uid='a' * 42))
        items = list(href for href, etag in s.list())
        assert len(items) == 2
        assert len(set(items)) == 2

    def test_specialchars(self, monkeypatch, requires_collections,
                          get_storage_args, get_item):
        if getattr(self, 'dav_server', '') == 'radicale':
            pytest.skip('Radicale is fundamentally broken.')

        monkeypatch.setattr('vdirsyncer.utils.generate_href', lambda x: x)

        uid = u'test @ foo ät bar град сатану'
        collection = 'test @ foo ät bar'

        s = self.storage_class(**get_storage_args(collection=collection))
        item = get_item(uid=uid)

        href, etag = s.upload(item)
        item2, etag2 = s.get(href)
        assert etag2 == etag
        assert_item_equals(item2, item)

        (href2, etag2), = s.list()
        assert etag2 == etag

        # https://github.com/owncloud/contacts/issues/581
        assert href2.replace('%2B', '%20') == href

        item2, etag2 = s.get(href)
        assert etag2 == etag
        assert_item_equals(item2, item)

        assert collection in urlunquote(s.collection)
        if self.storage_class.storage_name.endswith('dav'):
            assert urlquote(uid, '/@:') in href

    def test_metadata(self, requires_metadata, s):
        # https://github.com/owncloud/core/issues/18409
        if getattr(self, 'dav_server', '') == 'owncloud':
            pytest.skip('ownCloud is fundamentally broken.')

        try:
            s.set_meta('color', None)
            assert s.get_meta('color') is None
            s.set_meta('color', u'#ff0000')
            assert s.get_meta('color') == u'#ff0000'
        except exceptions.UnsupportedMetadataError:
            pass

        for x in (u'hello world', u'hello wörld'):
            s.set_meta('displayname', x)
            rv = s.get_meta('displayname')
            assert rv == x
            assert isinstance(rv, text_type)
