# -*- coding: utf-8 -*-


def to_unicode(x, encoding='ascii'):
    if not isinstance(x, str):
        x = x.decode(encoding)
    return x


def to_bytes(x, encoding='ascii'):
    if not isinstance(x, bytes):
        x = x.encode(encoding)
    return x
