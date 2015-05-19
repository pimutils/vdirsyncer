# -*- coding: utf-8 -*-

import sys

PY2 = sys.version_info[0] == 2


if PY2:  # pragma: no cover
    import urlparse
    from urllib import \
         quote as urlquote, \
         unquote as urlunquote
    text_type = unicode  # flake8: noqa
    iteritems = lambda x: x.iteritems()
    itervalues = lambda x: x.itervalues()
else:  # pragma: no cover
    import urllib.parse as urlparse
    urlquote = urlparse.quote
    urlunquote = urlparse.unquote
    text_type = str
    iteritems = lambda x: x.items()
    itervalues = lambda x: x.values()


def with_metaclass(meta, *bases):
    '''Original code from six, by Benjamin Peterson.'''
    class metaclass(meta):
        def __new__(cls, name, this_bases, d):
            return meta(name, bases, d)
    return type.__new__(metaclass, 'temporary_class', (), {})
