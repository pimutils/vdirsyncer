# -*- coding: utf-8 -*-

import errno
import logging
import os

from atomicwrites import atomic_write

from .base import normalize_meta_value
from ._rust import RustStorage
from .. import native
from ..utils import checkdir, expand_path

logger = logging.getLogger(__name__)


class FilesystemStorage(RustStorage):

    storage_name = 'filesystem'
    _repr_attributes = ('path',)

    def __init__(self, path, fileext, encoding='utf-8', post_hook=None,
                 **kwargs):
        super(FilesystemStorage, self).__init__(**kwargs)
        checkdir(expand_path(path), create=False)
        self.path = path
        self.encoding = encoding
        self.fileext = fileext
        self.post_hook = post_hook

        self._native_storage = native.ffi.gc(
            native.lib.vdirsyncer_init_filesystem(
                path.encode('utf-8'),
                fileext.encode('utf-8'),
                (post_hook or "").encode('utf-8')
            ),
            native.lib.vdirsyncer_storage_free
        )

    @classmethod
    def create_collection(cls, collection, **kwargs):
        kwargs = dict(kwargs)
        path = kwargs['path']

        if collection is not None:
            path = os.path.join(path, collection)

        checkdir(expand_path(path), create=True)

        kwargs['path'] = path
        kwargs['collection'] = collection
        return kwargs

    def get_meta(self, key):
        fpath = os.path.join(self.path, key)
        try:
            with open(fpath, 'rb') as f:
                return normalize_meta_value(f.read().decode(self.encoding))
        except IOError as e:
            if e.errno == errno.ENOENT:
                return u''
            else:
                raise

    def set_meta(self, key, value):
        value = normalize_meta_value(value)

        fpath = os.path.join(self.path, key)
        with atomic_write(fpath, mode='wb', overwrite=True) as f:
            f.write(value.encode(self.encoding))
