# -*- coding: utf-8 -*-
'''
    vdirsyncer.log
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''
import logging
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
                record.msg = prefix + record.msg

        return logging.Formatter.format(self, record)


class ClickStream(object):
    def write(self, string):
        click.echo(string.rstrip())


stdout_handler = logging.StreamHandler(ClickStream())
stdout_handler.formatter = ColorFormatter()
default_level = logging.INFO


def add_handler(handler):
    for logger in loggers.values():
        logger.addHandler(handler)


def create_logger(name):
    x = logging.getLogger(name)
    x.setLevel(default_level)
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
