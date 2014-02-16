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

class FilesystemStorage(Storage):
    '''Saves data in vdir collection, mtime is etag.'''
    def __init__(self, path, **kwargs):
        '''
        :param path: Absolute path to a *collection* inside a vdir.
        '''
        self.path = path
        super(FilesystemStorage, self).__init__(**kwargs)

    def _get_filepath(self, uid):
        return os.path.join(self.path, uid + self.fileext)

    def list(self):
        for fname in os.listdir(self.path):
            fpath = os.path.join(self.path, fname)
            if os.path.isfile(fpath) and fname.endswith(self.fileext):
                uid = fname[:-len(self.fileext)]
                yield uid, os.path.getmtime(fpath)

    def get(self, uid):
        fpath = self._get_filepath(uid)
        with open(fpath, 'rb') as f:
            return Item(f.read()), os.path.getmtime(fpath)

    def has(self, uid):
        return os.path.isfile(self._get_filepath(uid))

    def upload(self, obj):
        fpath = self._get_filepath(obj.uid)
        if os.path.exists(fpath):
            raise exceptions.AlreadyExistingError(obj.uid)
        with open(fpath, 'wb+') as f:
            f.write(obj.raw)
        return os.path.getmtime(fpath)

    def update(self, obj, etag):
        fpath = self._get_filepath(obj.uid)
        if not os.path.exists(fpath):
            raise exceptions.NotFoundError(obj.uid)
        actual_etag = os.path.getmtime(fpath)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)

        with open(fpath, 'wb') as f:
            f.write(obj.raw)
        return os.path.getmtime(fpath)

    def delete(self, uid, etag):
        fpath = self._get_filepath(uid)
        if not os.path.isfile(fpath):
            raise exceptions.NotFoundError(uid)
        actual_etag = os.path.getmtime(fpath)
        if etag != actual_etag:
            raise exceptions.WrongEtagError(etag, actual_etag)
        os.remove(fpath)
