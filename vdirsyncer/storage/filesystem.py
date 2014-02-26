# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.filesystem
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os
from vdirsyncer.storage.base import Storage, Item
import vdirsyncer.exceptions as exceptions
from vdirsyncer.utils import expand_path


class FilesystemStorage(Storage):

    '''Saves data in vdir collection
    mtime is etag
    filename without path is href'''

    def __init__(self, path, fileext, **kwargs):
        '''
        :param path: Absolute path to a *collection* inside a vdir.
        '''
        self.path = expand_path(path)
        self.fileext = fileext
        super(FilesystemStorage, self).__init__(**kwargs)

    def _get_filepath(self, href):
        return os.path.join(self.path, href)

    def _get_href(self, uid):
        return uid + self.fileext

    def list(self):
        for fname in os.listdir(self.path):
            fpath = os.path.join(self.path, fname)
            if os.path.isfile(fpath) and fname.endswith(self.fileext):
                yield fname, os.path.getmtime(fpath)

    def get(self, href):
        fpath = self._get_filepath(href)
        with open(fpath, 'rb') as f:
            return Item(f.read()), os.path.getmtime(fpath)

    def has(self, href):
        return os.path.isfile(self._get_filepath(href))

    def upload(self, obj):
        href = self._get_href(obj.uid)
        fpath = self._get_filepath(href)
        if os.path.exists(fpath):
            raise exceptions.AlreadyExistingError(obj.uid)
        with open(fpath, 'wb+') as f:
            f.write(obj.raw)
        return href, os.path.getmtime(fpath)

    def update(self, href, obj, etag):
        fpath = self._get_filepath(href)
        if href != self._get_href(obj.uid):
            raise exceptions.NotFoundError(obj.uid)
        if not os.path.exists(fpath):
            raise exceptions.NotFoundError(obj.uid)
        actual_etag = os.path.getmtime(fpath)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        with open(fpath, 'wb') as f:
            f.write(obj.raw)
        return os.path.getmtime(fpath)

    def delete(self, href, etag):
        fpath = self._get_filepath(href)
        if not os.path.isfile(fpath):
            raise exceptions.NotFoundError(href)
        actual_etag = os.path.getmtime(fpath)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)
        os.remove(fpath)
