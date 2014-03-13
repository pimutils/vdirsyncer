# -*- coding: utf-8 -*-
'''
    vdirsyncer.utils
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os


def expand_path(p):
    p = os.path.expanduser(p)
    p = os.path.abspath(p)
    return p


def split_dict(d, f):
    a = {}
    b = {}
    for k, v in d.items():
        if f(k):
            a[k] = v
        else:
            b[k] = v

    return a, b


def parse_options(items):
    for key, value in items:
        if value.lower() in ('yes', 'true', 'on'):
            value = True
        elif value.lower() in ('no', 'false', 'off'):
            value = False
        try:
            value = int(value)
        except ValueError:
            pass
        yield key, value
