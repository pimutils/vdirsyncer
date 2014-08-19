# -*- coding: utf-8 -*-
'''
    vdirsyncer.utils.doubleclick
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Utilities for writing multiprocessing applications with click.

    Currently the only relevant object here is the ``click`` object, which
    provides everything importable from click.  It also wraps some UI functions
    such that they don't produce overlapping output or prompt the user at the
    same time.

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import functools
import multiprocessing

UI_FUNCTIONS = frozenset(['echo', 'echo_via_pager', 'prompt', 'clear', 'edit',
                          'launch', 'getchar', 'pause'])


_ui_lock = multiprocessing.Lock()


def _ui_function(f):
    @functools.wraps(f)
    def inner(*a, **kw):
        _ui_lock.acquire()
        try:
            return f(*a, **kw)
        finally:
            _ui_lock.release()
    return inner


class _ClickProxy(object):
    def __init__(self, needs_wrapper, click=None):
        if click is None:
            import click
        self._click = click
        self._cache = {}
        self._needs_wrapper = frozenset(needs_wrapper)

    def __getattr__(self, name):
        if name not in self._cache:
            f = getattr(self._click, name)
            if name in self._needs_wrapper:
                f = _ui_function(f)
            self._cache[name] = f

        return self._cache[name]

click = _ClickProxy(UI_FUNCTIONS)
