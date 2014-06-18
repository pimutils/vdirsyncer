# -*- coding: utf-8 -*-
'''
    vdirsyncer.utils.compat
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import sys

PY2 = sys.version_info[0] == 2


if PY2:  # pragma: no cover
    import urlparse
    from urllib import \
         quote_plus as urlquote_plus, \
         unquote_plus as urlunquote_plus
    text_type = unicode  # flake8: noqa
    iteritems = lambda x: x.iteritems()
    itervalues = lambda x: x.itervalues()
else:  # pragma: no cover
    import urllib.parse as urlparse
    urlquote_plus = urlparse.quote_plus
    urlunquote_plus = urlparse.unquote_plus
    text_type = str
    iteritems = lambda x: x.items()
    itervalues = lambda x: x.values()
