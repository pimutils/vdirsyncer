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
