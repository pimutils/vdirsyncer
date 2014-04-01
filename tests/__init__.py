# -*- coding: utf-8 -*-
'''
    tests
    ~~~~~

    Test suite for vdirsyncer.

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import vdirsyncer.log
vdirsyncer.log.set_level(vdirsyncer.log.logging.DEBUG)


def normalize_item(item):
    # - X-RADICALE-NAME is used by radicale, because hrefs don't really exist
    #   in their filesystem backend
    # - PRODID is changed by radicale for some reason after upload, but nobody
    #   cares about that anyway
    rv = set()
    for line in item.raw.splitlines():
        line = line.strip()
        line = line.strip().split(u':', 1)
        if line[0] in ('X-RADICALE-NAME', 'PRODID', 'REV'):
            continue
        rv.add(u':'.join(line))
    return rv


def assert_item_equals(a, b):
    assert normalize_item(a) == normalize_item(b)
