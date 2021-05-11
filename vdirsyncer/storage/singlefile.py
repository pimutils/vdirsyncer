import collections
import contextlib
import functools
import glob
import logging
import os

from atomicwrites import atomic_write

from .. import exceptions
from ..utils import checkfile
from ..utils import expand_path
from ..utils import get_etag_from_file
from ..vobject import Item
from ..vobject import join_collection
from ..vobject import split_collection
from .base import Storage

logger = logging.getLogger(__name__)


def _writing_op(f):
    @functools.wraps(f)
    def inner(self, *args, **kwargs):
        if self._items is None or not self._at_once:
            self.list()
        rv = f(self, *args, **kwargs)
        if not self._at_once:
            self._write()
        return rv

    return inner


class SingleFileStorage(Storage):
    storage_name = "singlefile"
    _repr_attributes = ("path",)

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
    def discover(cls, path, **kwargs):
        if kwargs.pop("collection", None) is not None:
            raise TypeError("collection argument must not be given.")

        path = os.path.abspath(expand_path(path))
        try:
            path_glob = path % "*"
        except TypeError:
            # If not exactly one '%s' is present, we cannot discover
            # collections because we wouldn't know which name to assign.
            raise NotImplementedError()

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
    def create_collection(cls, collection, **kwargs):
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

    def list(self):
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

        if not text:
            return ()

        for item in split_collection(text):
            item = Item(item)
            etag = item.hash
            self._items[item.ident] = item, etag

        return ((href, etag) for href, (item, etag) in self._items.items())

    def get(self, href):
        if self._items is None or not self._at_once:
            self.list()

        try:
            return self._items[href]
        except KeyError:
            raise exceptions.NotFoundError(href)

    @_writing_op
    def upload(self, item):
        href = item.ident
        if href in self._items:
            raise exceptions.AlreadyExistingError(existing_href=href)

        self._items[href] = item, item.hash
        return href, item.hash

    @_writing_op
    def update(self, href, item, etag):
        if href not in self._items:
            raise exceptions.NotFoundError(href)

        _, actual_etag = self._items[href]
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        self._items[href] = item, item.hash
        return item.hash

    @_writing_op
    def delete(self, href, etag):
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

    @contextlib.contextmanager
    def at_once(self):
        self.list()
        self._at_once = True
        try:
            yield self
            self._write()
        finally:
            self._at_once = False
