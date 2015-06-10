# -*- coding: utf-8 -*-

import sys

PY2 = sys.version_info[0] == 2

if sys.version_info < (3, 3) and sys.version_info[:2] != (2, 7):
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


if PY2:  # pragma: no cover
    import urlparse
    import urllib as _urllib

    # Horrible hack to make urllib play nice with u'...' urls from requests
    def urlquote(x, *a, **kw):
        return _urllib.quote(to_native(x, 'utf-8'), *a, **kw)

    def urlunquote(x, *a, **kw):
        return _urllib.unquote(to_native(x, 'utf-8'), *a, **kw)

    text_type = unicode  # flake8: noqa
    iteritems = lambda x: x.iteritems()
    itervalues = lambda x: x.itervalues()
    to_native = to_bytes

else:  # pragma: no cover
    import urllib.parse as urlparse
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
