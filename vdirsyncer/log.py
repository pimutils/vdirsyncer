# -*- coding: utf-8 -*-
'''
    vdirsyncer.log
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''
import logging
import sys


class StdHandler(logging.StreamHandler):
    '''Required hack for supporting streams monkeypatched by click.'''
    def __init__(self, name):
        logging.Handler.__init__(self)
        self._name = name
        self.stream

    @property
    def stream(self):
        return getattr(sys, self._name)


stdout_handler = StdHandler('stdout')
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
