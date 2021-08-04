import aiostream
import pytest
from aioresponses import CallbackResult
from aioresponses import aioresponses

import vdirsyncer.storage.http
from vdirsyncer.storage.base import Storage
from vdirsyncer.storage.singlefile import SingleFileStorage

from . import StorageTests


class CombinedStorage(Storage):
    """A subclass of HttpStorage to make testing easier. It supports writes via
    SingleFileStorage."""

    _repr_attributes = ("url", "path")
    storage_name = "http_and_singlefile"

    def __init__(self, url, path, *, connector, **kwargs):
        if kwargs.get("collection", None) is not None:
            raise ValueError()

        super().__init__(**kwargs)
        self.url = url
        self.path = path
        self._reader = vdirsyncer.storage.http.HttpStorage(url=url, connector=connector)
        self._reader._ignore_uids = False
        self._writer = SingleFileStorage(path=path)

    async def list(self, *a, **kw):
        async for item in self._reader.list(*a, **kw):
            yield item

    async def get(self, *a, **kw):
        await aiostream.stream.list(self.list())
        return await self._reader.get(*a, **kw)

    async def upload(self, *a, **kw):
        return await self._writer.upload(*a, **kw)

    async def update(self, *a, **kw):
        return await self._writer.update(*a, **kw)

    async def delete(self, *a, **kw):
        return await self._writer.delete(*a, **kw)


class TestHttpStorage(StorageTests):
    storage_class = CombinedStorage
    supports_collections = False
    supports_metadata = False

    @pytest.fixture(autouse=True)
    def setup_tmpdir(self, tmpdir, monkeypatch):
        self.tmpfile = str(tmpdir.ensure("collection.txt"))

        def callback(url, headers, **kwargs):
            """Read our tmpfile at request time.

            We can't just read this during test setup since the file get written to
            during test execution.

            It might make sense to actually run a server serving the local file.
            """
            assert headers["User-Agent"].startswith("vdirsyncer/")

            with open(self.tmpfile) as f:
                body = f.read()

            return CallbackResult(
                status=200,
                body=body,
                headers={"Content-Type": "text/calendar; charset=utf-8"},
            )

        with aioresponses() as m:
            m.get("http://localhost:123/collection.txt", callback=callback, repeat=True)
            yield

    @pytest.fixture
    def get_storage_args(self, aio_connector):
        async def inner(collection=None):
            assert collection is None
            return {
                "url": "http://localhost:123/collection.txt",
                "path": self.tmpfile,
                "connector": aio_connector,
            }

        return inner
