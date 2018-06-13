# -*- coding: utf-8 -*-

import glob
import logging
import os

from .base import Storage
from ._rust import RustStorageMixin
from .. import native
from ..utils import checkfile, expand_path

logger = logging.getLogger(__name__)


class SingleFileStorage(RustStorageMixin, Storage):

    storage_name = 'singlefile'
    _repr_attributes = ('path',)

    _items = None
    _last_etag = None

    def __init__(self, path, **kwargs):
        super(SingleFileStorage, self).__init__(**kwargs)
        path = os.path.abspath(expand_path(path))
        checkfile(path, create=False)

        self.path = path

        self._native_storage = native.ffi.gc(
            native.lib.vdirsyncer_init_singlefile(path.encode('utf-8')),
            native.lib.vdirsyncer_storage_free
        )

    @classmethod
    def discover(cls, path, **kwargs):
        if kwargs.pop('collection', None) is not None:
            raise TypeError('collection argument must not be given.')

        path = os.path.abspath(expand_path(path))
        try:
            path_glob = path % '*'
        except TypeError:
            # If not exactly one '%s' is present, we cannot discover
            # collections because we wouldn't know which name to assign.
            raise NotImplementedError()

        placeholder_pos = path.index('%s')

        for subpath in glob.iglob(path_glob):
            if os.path.isfile(subpath):
                args = dict(kwargs)
                args['path'] = subpath

                collection_end = (
                    placeholder_pos +
                    2 +  # length of '%s'
                    len(subpath) - len(path)
                )
                collection = subpath[placeholder_pos:collection_end]
                args['collection'] = collection

                yield args

    @classmethod
    def create_collection(cls, collection, **kwargs):
        path = os.path.abspath(expand_path(kwargs['path']))

        if collection is not None:
            try:
                path = path % (collection,)
            except TypeError:
                raise ValueError('Exactly one %s required in path '
                                 'if collection is not null.')

        checkfile(path, create=True)
        kwargs['path'] = path
        kwargs['collection'] = collection
        return kwargs
