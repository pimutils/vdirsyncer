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


def _wrap_native(f, encoding='utf-8'):
    @functools.wraps(f)
    def wrapper(x, *a, **kw):
        to_orig = to_unicode if isinstance(x, text_type) else to_bytes
        return to_orig(f(to_native(x, encoding), *a, **kw), encoding)
    return wrapper


if PY2:  # pragma: no cover
    import urlparse
    import urllib as _urllib
    from inspect import getargspec as getargspec_ish  # noqa

    # Horrible hack to make urllib play nice with u'...' urls from requests
    urlquote = _wrap_native(_urllib.quote)
    urlunquote = _wrap_native(_urllib.unquote)

    text_type = unicode  # noqa
    iteritems = lambda x: x.iteritems()
    itervalues = lambda x: x.itervalues()
    to_native = to_bytes

else:  # pragma: no cover
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
