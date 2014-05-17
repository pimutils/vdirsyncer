# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.singlefile
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os
import collections

from .base import Item, Storage
import vdirsyncer.exceptions as exceptions
import vdirsyncer.log as log
from vdirsyncer.utils import expand_path, safe_write, itervalues
from vdirsyncer.utils.vobject import split_collection, join_collection

logger = log.get(__name__)


class SingleFileStorage(Storage):
    '''Save data in single VCALENDAR file, like Orage -- a calendar app for
    XFCE -- and Radicale do. Hashes are etags, UIDs or hashes are hrefs.

    This storage has many raceconditions and is very slow.'''

    _repr_attributes = ('path',)

    _write_mode = 'wb'
    _append_mode = 'ab'
    _read_mode = 'rb'

    _items = None

    def __init__(self, path, wrapper=None, encoding='utf-8', create=True,
                 collection=None, **kwargs):
        super(SingleFileStorage, self).__init__(**kwargs)
        path = expand_path(path)

        if collection is not None:
            raise ValueError('collection is not a valid argument for {}'
                             .format(type(self).__name__))

        if not os.path.isfile(path):
            if os.path.exists(path):
                raise IOError('{} is not a file.'.format(path))
            if create:
                self._write_mode = 'wb+'
                self._append_mode = 'ab+'
            else:
                raise IOError('File {} does not exist. Use create = '
                              'True in your configuration to automatically '
                              'create it, or create it '
                              'yourself.'.format(path))

        self.path = path
        self.encoding = encoding
        self.create = create
        self.wrapper = wrapper

    def list(self):
        self._items = collections.OrderedDict()

        try:
            with open(self.path, self._read_mode) as f:
                text = f.read().decode(self.encoding)
        except IOError as e:
            import errno
            if e.errno != errno.ENOENT or not self.create:  # file not found
                raise
            return ()

        rv = []
        for item in split_collection(text):
            item = Item(item)
            href = self._get_href(item)
            etag = item.hash
            self._items[href] = item, etag
            rv.append((href, etag))

        # we can't use yield here because we need to populate our
        # dict even if the user doesn't exhaust the iterator
        return rv

    def get(self, href):
        if self._items is None:
            self.list()

        try:
            return self._items[href]
        except KeyError:
            raise exceptions.NotFoundError(href)

    def upload(self, item):
        href = self._get_href(item)
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
        text = join_collection(
            (item.raw for item, etag in itervalues(self._items)),
            wrapper=self.wrapper
        )
        try:
            with safe_write(self.path, self._write_mode) as f:
                f.write(text.encode(self.encoding))
        finally:
            self._items = None
