from .. import exceptions, native
from .base import Storage
from ..vobject import Item
from functools import partial

import json


class RustStorage(Storage):
    _native_storage = None

    def _native(self, name):
        return partial(
            getattr(native.lib, 'vdirsyncer_storage_{}'.format(name)),
            self._native_storage
        )

    @classmethod
    def _static_native(cls, name):
        return getattr(
            native.lib,
            'vdirsyncer_storage_{}_{}'.format(name, cls.storage_name)
        )

    def list(self):
        e = native.get_error_pointer()
        listing = self._native('list')(e)
        native.check_error(e)
        listing = native.ffi.gc(listing,
                                native.lib.vdirsyncer_free_storage_listing)
        while native.lib.vdirsyncer_advance_storage_listing(listing):
            href = native.string_rv(
                native.lib.vdirsyncer_storage_listing_get_href(listing))
            etag = native.string_rv(
                native.lib.vdirsyncer_storage_listing_get_etag(listing))
            yield href, etag

    def get(self, href):
        href = href.encode('utf-8')
        e = native.get_error_pointer()
        result = self._native('get')(href, e)
        native.check_error(e)
        result = native.ffi.gc(result,
                               native.lib.vdirsyncer_free_storage_get_result)
        item = native.item_rv(result.item)
        etag = native.string_rv(result.etag)
        return Item(None, _native=item), etag

    # FIXME: implement get_multi

    def upload(self, item):
        e = native.get_error_pointer()
        result = self._native('upload')(item._native, e)
        native.check_error(e)
        result = native.ffi.gc(
            result, native.lib.vdirsyncer_free_storage_upload_result)
        href = native.string_rv(result.href)
        etag = native.string_rv(result.etag)
        return href, etag or None

    def update(self, href, item, etag):
        href = href.encode('utf-8')
        etag = etag.encode('utf-8')
        e = native.get_error_pointer()
        etag = self._native('update')(href, item._native, etag, e)
        native.check_error(e)
        return native.string_rv(etag) or None

    def delete(self, href, etag):
        href = href.encode('utf-8')
        etag = etag.encode('utf-8')
        e = native.get_error_pointer()
        self._native('delete')(href, etag, e)
        native.check_error(e)

    def buffered(self):
        self._native('buffered')()

    def flush(self):
        e = native.get_error_pointer()
        self._native('flush')(e)
        native.check_error(e)

    @classmethod
    def discover(cls, **kwargs):
        try:
            discover = cls._static_native('discover')
        except AttributeError:
            raise NotImplementedError()

        e = native.get_error_pointer()
        rv = discover(
            json.dumps(kwargs).encode('utf-8'),
            e
        )
        native.check_error(e)
        rv = native.string_rv(rv)
        return json.loads(rv)

    @classmethod
    def create_collection(cls, **kwargs):
        try:
            discover = cls._static_native('create')
        except AttributeError:
            raise NotImplementedError()

        e = native.get_error_pointer()
        rv = discover(
            json.dumps(kwargs).encode('utf-8'),
            e
        )
        native.check_error(e)
        rv = native.string_rv(rv)
        return json.loads(rv)

    def get_meta(self, key):
        enum_variant = _map_meta_key(key)
        e = native.get_error_pointer()
        rv = self._native('get_meta')(enum_variant, e)
        native.check_error(e)
        return native.string_rv(rv)

    def set_meta(self, key, value):
        enum_variant = _map_meta_key(key)
        e = native.get_error_pointer()
        self._native('set_meta')(
            enum_variant,
            (value or '').encode('utf-8'),
            e
        )
        native.check_error(e)

    def delete_collection(self):
        e = native.get_error_pointer()
        self._native('delete_collection')(e)
        native.check_error(e)


def _map_meta_key(key):
    try:
        return {
            'color': native.lib.Color,
            'displayname': native.lib.Displayname
        }[key.lower()]
    except KeyError:
        raise exceptions.UnsupportedMetadataError()
