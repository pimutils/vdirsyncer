# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.singlefile
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import collections
import os

from .base import Item, Storage
from .. import exceptions, log
from ..utils import checkfile, expand_path, safe_write
from ..utils.compat import iteritems, itervalues
from ..utils.vobject import join_collection, split_collection

logger = log.get(__name__)


class SingleFileStorage(Storage):
    '''Save data in single ``.vcf`` or ``.ics`` file. Usable as ``singlefile``
    in the config file.

    The storage basically guesses how items should be joined in the file.

    .. versionadded:: 0.1.6

    .. note::
        This storage has many raceconditions, which basically means that you
        should avoid changing the file with another program (or even running
        any programs which might modify the file) while vdirsyncer is running.

        Also it is currently very slow, so you should consider limiting the
        amount of items you synchronize. In combination with
        :py:class:`vdirsyncer.storage.CaldavStorage` this can be achieved via
        the ``start_date`` and ``end_date`` parameters.

    :param path: The filepath to the file to be written to.
    :param encoding: Which encoding the file should use. Defaults to UTF-8.
    :param create: Create the file if it does not exist.

    Example for syncing with :py:class:`vdirsyncer.storage.CaldavStorage`::

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

    def __init__(self, path, encoding='utf-8', create=True, **kwargs):
        super(SingleFileStorage, self).__init__(**kwargs)
        path = expand_path(path)

        collection = kwargs.get('collection')
        if collection is not None:
            raise ValueError('collection is not a valid argument for {}'
                             .format(type(self).__name__))

        checkfile(path, create=create)

        if create:
            self._write_mode = 'wb+'
            self._append_mode = 'ab+'

        self.path = path
        self.encoding = encoding
        self.create = create

    def list(self):
        self._items = collections.OrderedDict()

        try:
            self._last_mtime = os.path.getmtime(self.path)
            with open(self.path, self._read_mode) as f:
                text = f.read().decode(self.encoding)
        except OSError as e:
            import errno
            if e.errno != errno.ENOENT or not self.create:  # file not found
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
        if self._items is None:
            self.list()

        try:
            return self._items[href]
        except KeyError:
            raise exceptions.NotFoundError(href)

    def upload(self, item):
        href = item.ident
        self.list()
        if href in self._items:
            raise exceptions.AlreadyExistingError(href)

        self._items[href] = item, item.hash
        self._write()
        return href, item.hash

    def update(self, href, item, etag):
        self.list()
        if href not in self._items:
            raise exceptions.NotFoundError(href)

        _, actual_etag = self._items[href]
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        self._items[href] = item, item.hash
        self._write()
        return item.hash

    def delete(self, href, etag):
        self.list()
        if href not in self._items:
            raise exceptions.NotFoundError(href)

        _, actual_etag = self._items[href]
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        del self._items[href]
        self._write()

    def _write(self):
        if self._last_mtime is not None and \
           self._last_mtime != os.path.getmtime(self.path):
            raise exceptions.PreconditionFailed(
                'Some other program modified the file {r!}'.format(self.path))
        text = join_collection(
            (item.raw for item, etag in itervalues(self._items)),
        )
        try:
            with safe_write(self.path, self._write_mode) as f:
                f.write(text.encode(self.encoding))
        finally:
            self._items = None
            self._last_mtime = None
