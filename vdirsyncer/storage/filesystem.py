# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.filesystem
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import os

from .base import Item, Storage
from .. import exceptions, log
from ..utils import checkdir, expand_path, get_etag_from_file, safe_write
from ..utils.compat import text_type

logger = log.get(__name__)


class FilesystemStorage(Storage):

    '''
    Saves each item in its own file, given a directory.

    Can be used with `khal <http://lostpackets.de/khal/>`_. See :doc:`vdir` for
    a more formal description of the format.

    :param path: Absolute path to a vdir or collection, depending on the
        collection parameter (see :py:class:`vdirsyncer.storage.base.Storage`).
    :param fileext: The file extension to use (e.g. ``.txt``). Contained in the
        href, so if you change the file extension after a sync, this will
        trigger a re-download of everything (but *should* not cause data-loss
        of any kind).
    :param encoding: File encoding for items.
    :param create: Create directories if they don't exist.
    '''

    storage_name = 'filesystem'
    _repr_attributes = ('path',)

    def __init__(self, path, fileext, encoding='utf-8', **kwargs):
        super(FilesystemStorage, self).__init__(**kwargs)
        path = expand_path(path)
        checkdir(path, create=False)
        self.path = path
        self.encoding = encoding
        self.fileext = fileext

    @classmethod
    def discover(cls, path, **kwargs):
        if kwargs.pop('collection', None) is not None:
            raise TypeError('collection argument must not be given.')
        path = expand_path(path)
        try:
            collections = os.listdir(path)
        except OSError:
            if not kwargs.get('create', True):
                raise
        else:
            for collection in collections:
                collection_path = os.path.join(path, collection)
                if os.path.isdir(collection_path):
                    args = dict(collection=collection, path=collection_path,
                                **kwargs)
                    yield args

    @classmethod
    def create_collection(cls, collection, **kwargs):
        kwargs['path'] = path = os.path.join(kwargs['path'], collection)
        checkdir(path, create=True)
        return kwargs

    def _get_filepath(self, href):
        return os.path.join(self.path, href)

    def _get_href(self, item):
        # XXX: POSIX only defines / and \0 as invalid chars, but we should make
        # this work crossplatform.
        return item.ident.replace('/', '_') + self.fileext

    def list(self):
        for fname in os.listdir(self.path):
            fpath = os.path.join(self.path, fname)
            if os.path.isfile(fpath) and fname.endswith(self.fileext):
                yield fname, get_etag_from_file(fpath)

    def get(self, href):
        fpath = self._get_filepath(href)
        try:
            with open(fpath, 'rb') as f:
                return (Item(f.read().decode(self.encoding)),
                        get_etag_from_file(fpath))
        except IOError as e:
            import errno
            if e.errno == errno.ENOENT:
                raise exceptions.NotFoundError(href)
            else:
                raise

    def upload(self, item):
        href = self._get_href(item)
        fpath = self._get_filepath(href)
        if os.path.exists(fpath):
            raise exceptions.AlreadyExistingError(item)

        if not isinstance(item.raw, text_type):
            raise TypeError('item.raw must be a unicode string.')

        with safe_write(fpath, 'wb+') as f:
            f.write(item.raw.encode(self.encoding))
            return href, f.get_etag()

    def update(self, href, item, etag):
        fpath = self._get_filepath(href)
        if href != self._get_href(item) and item.uid:
            logger.warning('href != uid + fileext: href={}; uid={}'
                           .format(href, item.uid))
        if not os.path.exists(fpath):
            raise exceptions.NotFoundError(item.uid)
        actual_etag = get_etag_from_file(fpath)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        if not isinstance(item.raw, text_type):
            raise TypeError('item.raw must be a unicode string.')

        with safe_write(fpath, 'wb') as f:
            f.write(item.raw.encode(self.encoding))
            return f.get_etag()

    def delete(self, href, etag):
        fpath = self._get_filepath(href)
        if not os.path.isfile(fpath):
            raise exceptions.NotFoundError(href)
        actual_etag = get_etag_from_file(fpath)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)
        os.remove(fpath)
