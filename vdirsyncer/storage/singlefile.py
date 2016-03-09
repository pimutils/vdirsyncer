# -*- coding: utf-8 -*-

import collections
import contextlib
import functools
import logging
import os

from atomicwrites import atomic_write

from .base import Item, Storage
from .. import exceptions
from ..utils import checkfile, expand_path
from ..utils.compat import iteritems, itervalues
from ..utils.vobject import join_collection, split_collection

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
    '''Save data in single local ``.vcf`` or ``.ics`` file.

    The storage basically guesses how items should be joined in the file.

    .. versionadded:: 0.1.6

    .. note::
        This storage is very slow, and that is unlikely to change. You should
        consider using :storage:`filesystem` if it fits your usecase.

    :param path: The filepath to the file to be written to.
    :param encoding: Which encoding the file should use. Defaults to UTF-8.

    Example for syncing with :storage:`caldav`::

        [pair my_calendar]
        a = my_calendar_local
        b = my_calendar_remote

        [storage my_calendar_local]
        type = singlefile
        path = ~/my_calendar.ics

        [storage my_calendar_remote]
        type = caldav
        url = https://caldav.example.org/username/my_calendar/
        #username =
        #password =

    '''

    storage_name = 'singlefile'
    _repr_attributes = ('path',)

    _write_mode = 'wb'
    _append_mode = 'ab'
    _read_mode = 'rb'

    _items = None
    _last_mtime = None

    def __init__(self, path, encoding='utf-8', **kwargs):
        super(SingleFileStorage, self).__init__(**kwargs)
        path = os.path.abspath(expand_path(path))

        collection = kwargs.get('collection')
        if collection is not None:
            raise exceptions.UserError(
                'collection is not a valid argument for {}'
                .format(type(self).__name__)
            )

        checkfile(path, create=False)

        self.path = path
        self.encoding = encoding
        self._at_once = False

    @classmethod
    def create_collection(cls, collection, **kwargs):
        if collection is not None:
            raise ValueError('collection is not a valid argument for {}'
                             .format(cls.__name__))

        path = os.path.abspath(expand_path(kwargs['path']))
        checkfile(path, create=True)
        return kwargs

    def list(self):
        self._items = collections.OrderedDict()

        try:
            self._last_mtime = os.path.getmtime(self.path)
            with open(self.path, self._read_mode) as f:
                text = f.read().decode(self.encoding)
        except OSError as e:
            import errno
            if e.errno != errno.ENOENT:  # file not found
                raise IOError(e)
            text = None

        if not text:
            return ()

        for item in split_collection(text):
            item = Item(item)
            etag = item.hash
            self._items[item.ident] = item, etag

        return ((href, etag) for href, (item, etag) in iteritems(self._items))

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
        if self._last_mtime is not None and \
           self._last_mtime != os.path.getmtime(self.path):
            raise exceptions.PreconditionFailed(
                'Some other program modified the file {r!}. Re-run the '
                'synchronization and make sure absolutely no other program is '
                'writing into the same file.'.format(self.path))
        text = join_collection(
            (item.raw for item, etag in itervalues(self._items)),
        )
        try:
            with atomic_write(self.path, mode='wb', overwrite=True) as f:
                f.write(text.encode(self.encoding))
        finally:
            self._items = None
            self._last_mtime = None

    @contextlib.contextmanager
    def at_once(self):
        self.list()
        self._at_once = True
        try:
            yield self
        except:
            raise
        else:
            self._write()
        finally:
            self._at_once = False
