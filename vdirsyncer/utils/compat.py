# -*- coding: utf-8 -*-
'''
    vdirsyncer.utils.compat
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import sys

PY2 = sys.version_info[0] == 2


if PY2:
    import urlparse
    from urllib import \
         quote_plus as urlquote_plus, \
         unquote_plus as urlunquote_plus
    text_type = unicode  # flake8: noqa
    iteritems = lambda x: x.iteritems()
    itervalues = lambda x: x.itervalues()
    get_raw_input = raw_input
else:
    import urllib.parse as urlparse
    urlquote_plus = urlparse.quote_plus
    urlunquote_plus = urlparse.unquote_plus
    text_type = str
    iteritems = lambda x: x.items()
    itervalues = lambda x: x.values()
    get_raw_input = input
