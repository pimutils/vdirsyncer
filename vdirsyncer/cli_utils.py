# -*- coding: utf-8 -*-
'''
    watdo.cli_utils
    ~~~~~~~~~

    This module contains helper functions that should be useful for arbitrary
    CLI interfaces.

    :copyright: (c) 2013 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os
import sys


def bail_out(msg):
    print(msg)
    sys.exit(1)


def check_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)


def path(p):
    p = os.path.expanduser(p)
    p = os.path.abspath(p)
    return p


def confirm(message='Are you sure? (Y/n)'):
    inp = raw_input(message).lower().strip()
    if not inp or inp == 'y':
        return True
    return False
