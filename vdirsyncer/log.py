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
default_level = logging.INFO


def create_logger(name):
    x = logging.getLogger(name)
    x.setLevel(default_level)
    x.addHandler(stdout_handler)
    return x


loggers = {}


def get(name):
    assert name.startswith('vdirsyncer.')
    if name not in loggers:
        loggers[name] = create_logger(name)
    return loggers[name]


def set_level(level):
    global default_level
    default_level = level
    for logger in loggers.values():
        logger.setLevel(level)
