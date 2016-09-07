# -*- coding: utf-8 -*-

import sys

from inspect import getfullargspec as getargspec_ish  # noqa


def to_unicode(x, encoding='ascii'):
    if not isinstance(x, str):
        x = x.decode(encoding)
    return x


def to_bytes(x, encoding='ascii'):
    if not isinstance(x, bytes):
        x = x.encode(encoding)
    return x
