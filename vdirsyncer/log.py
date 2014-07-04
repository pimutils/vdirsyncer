# -*- coding: utf-8 -*-
'''
    vdirsyncer.log
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''
import logging
import sys

import click


class ColorFormatter(logging.Formatter):
    colors = {
        'error': dict(fg='red'),
        'exception': dict(fg='red'),
        'critical': dict(fg='red'),
        'debug': dict(fg='blue'),
        'warning': dict(fg='yellow')
    }

    def format(self, record):
        if not record.exc_info:
            level = record.levelname.lower()
            if level in self.colors:
                prefix = click.style('{}: '.format(level),
                                     **self.colors[level])
                record.msg = '\n'.join(prefix + x
                                       for x in str(record.msg).splitlines())

        return logging.Formatter.format(self, record)


class ClickStream(object):
    def write(self, string):
        click.echo(string, file=sys.stderr, nl=False)


stdout_handler = logging.StreamHandler(ClickStream())
stdout_handler.formatter = ColorFormatter()

_level = logging.INFO
_handlers = []

_loggers = {}


def get(name):
    assert name.startswith('vdirsyncer.')
    if name not in _loggers:
        _loggers[name] = x = logging.getLogger(name)
        x.handlers = _handlers
        x.setLevel(_level)

    return _loggers[name]


def add_handler(handler):
    if handler not in _handlers:
        _handlers.append(handler)


def set_level(level):
    global _level
    _level = level
    for logger in _loggers.values():
        logger.setLevel(_level)
