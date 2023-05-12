import collections
import contextlib
import functools
import glob
import logging
import os
from typing import Iterable

from atomicwrites import atomic_write

from .. import exceptions
from ..utils import checkfile
from ..utils import expand_path
from ..utils import get_etag_from_file
from ..utils import uniq
from ..vobject import Item
from ..vobject import join_collection
from ..vobject import split_collection
from .base import Storage

logger = logging.getLogger(__name__)


def _writing_op(f):
    @functools.wraps(f)
    async def inner(self, *args, **kwargs):
        if self._items is None or not self._at_once:
            async for _ in self.list():
                pass
        assert self._items is not None
        rv = await f(self, *args, **kwargs)
        if not self._at_once:
            self._write()
        return rv

    return inner


class SingleFileStorage(Storage):
    storage_name = "singlefile"
    _repr_attributes = ["path"]

    _write_mode = "wb"
    _append_mode = "ab"
    _read_mode = "rb"

    _items = None
    _last_etag = None

    def __init__(self, path, encoding="utf-8", **kwargs):
        super().__init__(**kwargs)
        path = os.path.abspath(expand_path(path))
        checkfile(path, create=False)

        self.path = path
        self.encoding = encoding
        self._at_once = False

    @classmethod
    async def discover(cls, path, **kwargs):
        if kwargs.pop("collection", None) is not None:
            raise TypeError("collection argument must not be given.")

        path = os.path.abspath(expand_path(path))
        try:
            path_glob = path % "*"
        except TypeError:
            # If not exactly one '%s' is present, we cannot discover
            # collections because we wouldn't know which name to assign.
            raise NotImplementedError

        placeholder_pos = path.index("%s")

        for subpath in glob.iglob(path_glob):
            if os.path.isfile(subpath):
                args = dict(kwargs)
                args["path"] = subpath

                collection_end = (
                    placeholder_pos + 2 + len(subpath) - len(path)  # length of '%s'
                )
                collection = subpath[placeholder_pos:collection_end]
                args["collection"] = collection

                yield args

    @classmethod
    async def create_collection(cls, collection, **kwargs):
        path = os.path.abspath(expand_path(kwargs["path"]))

        if collection is not None:
            try:
                path = path % (collection,)
            except TypeError:
                raise ValueError(
                    "Exactly one %s required in path " "if collection is not null."
                )

        checkfile(path, create=True)
        kwargs["path"] = path
        kwargs["collection"] = collection
        return kwargs

    async def list(self):
        self._items = collections.OrderedDict()

        try:
            self._last_etag = get_etag_from_file(self.path)
            with open(self.path, self._read_mode) as f:
                text = f.read().decode(self.encoding)
        except OSError as e:
            import errno

            if e.errno != errno.ENOENT:  # file not found
                raise OSError(e)
            text = None

        if text:
            for item in split_collection(text):
                item = Item(item)
                etag = item.hash
                href = item.ident
                self._items[href] = item, etag

                yield href, etag

    async def get(self, href):
        if self._items is None or not self._at_once:
            async for _ in self.list():
                pass

        try:
            return self._items[href]
        except KeyError:
            raise exceptions.NotFoundError(href)

    async def get_multi(self, hrefs: Iterable[str]):
        async with self.at_once():
            for href in uniq(hrefs):
                item, etag = await self.get(href)
                yield href, item, etag

    @_writing_op
    async def upload(self, item):
        href = item.ident
        if href in self._items:
            raise exceptions.AlreadyExistingError(existing_href=href)

        self._items[href] = item, item.hash
        return href, item.hash

    @_writing_op
    async def update(self, href, item, etag):
        if href not in self._items:
            raise exceptions.NotFoundError(href)

        _, actual_etag = self._items[href]
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        self._items[href] = item, item.hash
        return item.hash

    @_writing_op
    async def delete(self, href, etag):
        if href not in self._items:
            raise exceptions.NotFoundError(href)

        _, actual_etag = self._items[href]
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        del self._items[href]

    def _write(self):
        if self._last_etag is not None and self._last_etag != get_etag_from_file(
            self.path
        ):
            raise exceptions.PreconditionFailed(
                (
                    "Some other program modified the file {!r}. Re-run the "
                    "synchronization and make sure absolutely no other program is "
                    "writing into the same file."
                ).format(self.path)
            )
        text = join_collection(item.raw for item, etag in self._items.values())
        try:
            with atomic_write(self.path, mode="wb", overwrite=True) as f:
                f.write(text.encode(self.encoding))
        finally:
            self._items = None
            self._last_etag = None

    @contextlib.asynccontextmanager
    async def at_once(self):
        async for _ in self.list():
            pass
        self._at_once = True
        try:
            yield self
            self._write()
        finally:
            self._at_once = False
