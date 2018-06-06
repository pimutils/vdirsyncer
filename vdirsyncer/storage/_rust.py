from .. import native
from ..vobject import Item
from functools import partial


class RustStorageMixin:
    _native_storage = None

    def _native(self, name):
        return partial(
            getattr(native.lib, 'vdirsyncer_storage_{}'.format(name)),
            self._native_storage
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
