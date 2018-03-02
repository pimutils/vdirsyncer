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
    '''Save data in single local ``.vcf`` or ``.ics`` file.

    The storage basically guesses how items should be joined in the file.

    .. versionadded:: 0.1.6

    .. note::
        This storage is very slow, and that is unlikely to change. You should
        consider using :storage:`filesystem` if it fits your usecase.

    :param path: The filepath to the file to be written to. If collections are
        used, this should contain ``%s`` as a placeholder for the collection
        name.
    :param encoding: Which encoding the file should use. Defaults to UTF-8.

    Example for syncing with :storage:`caldav`::

        [pair my_calendar]
        a = my_calendar_local
        b = my_calendar_remote
        collections = ["from a", "from b"]

        [storage my_calendar_local]
        type = "singlefile"
        path = ~/.calendars/%s.ics

        [storage my_calendar_remote]
        type = "caldav"
        url = https://caldav.example.org/
        #username =
        #password =

    Example for syncing with :storage:`caldav` using a ``null`` collection::

        [pair my_calendar]
        a = my_calendar_local
        b = my_calendar_remote

        [storage my_calendar_local]
        type = "singlefile"
        path = ~/my_calendar.ics

        [storage my_calendar_remote]
        type = "caldav"
        url = https://caldav.example.org/username/my_calendar/
        #username =
        #password =

    '''

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
