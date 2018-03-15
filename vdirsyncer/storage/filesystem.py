# -*- coding: utf-8 -*-

import errno
import logging
import os

from atomicwrites import atomic_write

from .base import Storage, normalize_meta_value
from ._rust import RustStorageMixin
from .. import native
from ..utils import checkdir, expand_path

logger = logging.getLogger(__name__)


class FilesystemStorage(RustStorageMixin, Storage):

    '''
    Saves each item in its own file, given a directory.

    Can be used with `khal <http://lostpackets.de/khal/>`_. See :doc:`vdir` for
    a more formal description of the format.

    Directories with a leading dot are ignored to make usage of e.g. version
    control easier.

    :param path: Absolute path to a vdir/collection. If this is used in
        combination with the ``collections`` parameter in a pair-section, this
        should point to a directory of vdirs instead.
    :param fileext: The file extension to use (e.g. ``.txt``). Contained in the
        href, so if you change the file extension after a sync, this will
        trigger a re-download of everything (but *should* not cause data-loss
        of any kind).
    :param encoding: File encoding for items, both content and filename.
    :param post_hook: A command to call for each item creation and
        modification. The command will be called with the path of the
        new/updated file.
    '''

    storage_name = 'filesystem'
    _repr_attributes = ('path',)

    def __init__(self, path, fileext, encoding='utf-8', post_hook=None,
                 **kwargs):
        super(FilesystemStorage, self).__init__(**kwargs)
        path = expand_path(path)
        checkdir(path, create=False)
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
    def discover(cls, path, **kwargs):
        if kwargs.pop('collection', None) is not None:
            raise TypeError('collection argument must not be given.')
        path = expand_path(path)
        try:
            collections = os.listdir(path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        else:
            for collection in collections:
                collection_path = os.path.join(path, collection)
                if not cls._validate_collection(collection_path):
                    continue
                args = dict(collection=collection, path=collection_path,
                            **kwargs)
                yield args

    @classmethod
    def _validate_collection(cls, path):
        if not os.path.isdir(path):
            return False
        if os.path.basename(path).startswith('.'):
            return False
        return True

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
