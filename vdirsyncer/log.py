# -*- coding: utf-8 -*-
'''
    vdirsyncer.log
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
import logging
import sys


stdout_handler = logging.StreamHandler(sys.stdout)


def create_logger(name):
    x = logging.getLogger(name)
    x.setLevel(logging.WARNING)
    x.addHandler(stdout_handler)
    return x


loggers = {}


def get(name):
    name = 'watdo.' + name
    if name not in loggers:
        loggers[name] = create_logger(name)
    return loggers[name]
