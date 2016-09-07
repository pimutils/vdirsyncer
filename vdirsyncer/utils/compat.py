# -*- coding: utf-8 -*-

import sys

from inspect import getfullargspec as getargspec_ish  # noqa

PY2 = sys.version_info[0] == 2

if sys.version_info < (3, 3) and \
   sys.version_info[:2] != (2, 7):  # pragma: no cover
    raise RuntimeError(
        'vdirsyncer only works on Python versions 2.7.x and 3.3+'
    )


def to_unicode(x, encoding='ascii'):
    if not isinstance(x, str):
        x = x.decode(encoding)
    return x


def to_bytes(x, encoding='ascii'):
    if not isinstance(x, bytes):
        x = x.encode(encoding)
    return x
