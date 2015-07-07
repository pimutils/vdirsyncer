# -*- coding: utf-8 -*-

import pytest

from requests import Response

from vdirsyncer.storage.base import Storage
import vdirsyncer.storage.http
from vdirsyncer.storage.singlefile import SingleFileStorage

from . import StorageTests


class CombinedStorage(Storage):
    '''A subclass of HttpStorage to make testing easier. It supports writes via
    SingleFileStorage.'''
    _repr_attributes = ('url', 'path')

    def __init__(self, url, path, **kwargs):
        super(CombinedStorage, self).__init__(**kwargs)
        self.url = url
        self.path = path
        self._reader = vdirsyncer.storage.http.HttpStorage(url=url)
        self._writer = SingleFileStorage(path=path)

    def list(self, *a, **kw):
        return self._reader.list(*a, **kw)

    def get(self, *a, **kw):
        self.list()
        return self._reader.get(*a, **kw)

    def upload(self, *a, **kw):
        return self._writer.upload(*a, **kw)

    def update(self, *a, **kw):
        return self._writer.update(*a, **kw)

    def delete(self, *a, **kw):
        return self._writer.delete(*a, **kw)


class TestHttpStorage(StorageTests):
    storage_class = CombinedStorage
    supports_collections = False
    supports_metadata = False

    @pytest.fixture(autouse=True)
    def setup_tmpdir(self, tmpdir, monkeypatch):
        self.tmpfile = str(tmpdir.ensure('collection.txt'))

        def _request(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url == 'http://localhost:123/collection.txt'
            assert 'vdirsyncer' in kwargs['headers']['User-Agent']
            r = Response()
            r.status_code = 200
            try:
                with open(self.tmpfile, 'rb') as f:
                    r._content = f.read()
            except IOError:
                r._content = b''

            r.headers['Content-Type'] = 'text/icalendar'
            r.encoding = 'utf-8'
            return r

        monkeypatch.setattr(vdirsyncer.storage.http, 'request', _request)

    @pytest.fixture
    def get_storage_args(self):
        def inner(collection=None):
            assert collection is None
            return {'url': 'http://localhost:123/collection.txt',
                    'path': self.tmpfile}
        return inner
