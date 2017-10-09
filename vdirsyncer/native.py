from ._native import ffi, lib
from .exceptions import VobjectParseError


def parse_component(raw):
    e = ffi.new('VdirsyncerError *')
    try:
        c = lib.vdirsyncer_parse_component(raw, e)
        if e.failed:
            raise VobjectParseError(ffi.string(e.msg).decode('utf-8'))
        return _component_rv(c)
    finally:
        if e.failed:
            lib.vdirsyncer_clear_err(e)


def write_component(component):
    return _string_rv(lib.vdirsyncer_write_component(component))


def get_uid(component):
    return _string_rv(lib.vdirsyncer_get_uid(component))


def _string_rv(c_str):
    try:
        return ffi.string(c_str).decode('utf-8')
    finally:
        lib.vdirsyncer_free_str(c_str)


def change_uid(component, uid):
    lib.vdirsyncer_change_uid(component, uid.encode('utf-8'))


def _component_rv(c):
    return ffi.gc(c, lib.vdirsyncer_free_component)


def clone_component(c):
    return _component_rv(lib.vdirsyncer_clone_component(c))


def hash_component(c):
    return _string_rv(lib.vdirsyncer_hash_component(c))
