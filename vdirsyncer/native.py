import os

import shippai

from . import exceptions
from ._native import ffi, lib

lib.vdirsyncer_init_logger()

rust_basepath = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    '../rust/'
))

errors = shippai.Shippai(ffi, lib, rust_basepath=rust_basepath)


def string_rv(c_str):
    try:
        return ffi.string(c_str).decode('utf-8')
    finally:
        lib.vdirsyncer_free_str(c_str)


def item_rv(c):
    return ffi.gc(c, lib.vdirsyncer_free_item)


def get_error_pointer():
    return ffi.new("ShippaiError **")


def check_error(e):
    try:
        errors.check_exception(e[0])
    except errors.Error.ItemNotFound as e:
        raise exceptions.NotFoundError(e) from e
    except errors.Error.ItemAlreadyExisting as e:
        raise exceptions.AlreadyExistingError(e) from e
    except errors.Error.WrongEtag as e:
        raise exceptions.WrongEtagError(e) from e
    except errors.Error.ReadOnly as e:
        raise exceptions.ReadOnlyError(e) from e
    except errors.Error.UnsupportedVobject as e:
        raise exceptions.UnsupportedVobjectError(e) from e
    except (errors.Error.BadDiscoveryConfig,
            errors.Error.BadCollectionConfig) as e:
        raise TypeError(e) from e
    except errors.Error.MetadataValueUnsupported as e:
        raise exceptions.UnsupportedMetadataError(e) from e
