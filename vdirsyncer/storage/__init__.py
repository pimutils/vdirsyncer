# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage
    ~~~~~~~~~~~~~~~~~~

    There are storage classes which control the access to one vdir-collection
    and offer basic CRUD-ish methods for modifying those collections. The exact
    interface is described in `vdirsyncer.storage.base`, the `Storage` class
    should be a superclass of all storage classes.

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

from .dav import CaldavStorage, CarddavStorage
from .filesystem import FilesystemStorage
from .http import HttpStorage
from .singlefile import SingleFileStorage


def _generate_storage_dict(*classes):
    rv = {}
    for cls in classes:
        key = cls.storage_name
        assert key
        assert isinstance(key, str)
        assert key not in rv
        rv[key] = cls
    return rv

storage_names = _generate_storage_dict(
    CaldavStorage,
    CarddavStorage,
    FilesystemStorage,
    HttpStorage,
    SingleFileStorage
)

del _generate_storage_dict
