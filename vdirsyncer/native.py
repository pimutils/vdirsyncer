from ._native import ffi, lib
from . import exceptions


def string_rv(c_str):
    try:
        return ffi.string(c_str).decode('utf-8')
    finally:
        lib.vdirsyncer_free_str(c_str)


def item_rv(c):
    return ffi.gc(c, lib.vdirsyncer_free_item)


def check_error(e):
    try:
        if e.failed:
            msg = ffi.string(e.msg).decode('utf-8')
            if msg.startswith('ItemNotFound'):
                raise exceptions.NotFoundError(msg)
            elif msg.startswith('AlreadyExisting'):
                raise exceptions.AlreadyExistingError(msg)
            elif msg.startswith('WrongEtag'):
                raise exceptions.WrongEtagError(msg)
            elif msg.startswith('ItemUnparseable'):
                raise ValueError(msg)
            else:
                raise Exception(msg)
    finally:
        if e.failed:
            lib.vdirsyncer_clear_err(e)
