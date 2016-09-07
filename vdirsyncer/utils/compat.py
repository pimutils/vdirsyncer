# -*- coding: utf-8 -*-

import functools
import sys

PY2 = sys.version_info[0] == 2

if sys.version_info < (3, 3) and \
   sys.version_info[:2] != (2, 7):  # pragma: no cover
    raise RuntimeError(
        'vdirsyncer only works on Python versions 2.7.x and 3.3+'
    )


def to_unicode(x, encoding='ascii'):
    if not isinstance(x, text_type):
        x = x.decode(encoding)
    return x


def to_bytes(x, encoding='ascii'):
    if not isinstance(x, bytes):
        x = x.encode(encoding)
    return x


import urllib.parse as urlparse
from inspect import getfullargspec as getargspec_ish  # noqa

urlquote = urlparse.quote
urlunquote = urlparse.unquote
text_type = str
iteritems = lambda x: x.items()
itervalues = lambda x: x.values()
to_native = to_unicode


def with_metaclass(meta, *bases):
    '''Original code from six, by Benjamin Peterson.'''
    class metaclass(meta):
        def __new__(cls, name, this_bases, d):
            return meta(name, bases, d)
    return type.__new__(metaclass, 'temporary_class', (), {})
