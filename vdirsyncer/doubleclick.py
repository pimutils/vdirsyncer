# -*- coding: utf-8 -*-
'''
Utilities for writing threaded applications with click:

- There is a global ``ctx`` object to be used.

- The ``click`` object's attributes are supposed to be used instead of the
  click package's content.

  - It wraps some UI functions such that they don't produce overlapping
    output or prompt the user at the same time.

  - It wraps BaseCommand subclasses such that their invocation changes the
    ctx global, and also changes the shortcut decorators to use the new
    classes.
'''

import functools
import threading


class _ClickProxy(object):
    def __init__(self, wrappers, click=None):
        if click is None:
            import click
        self._click = click
        self._cache = {}
        self._wrappers = dict(wrappers)

    def __getattr__(self, name):
        if name not in self._cache:
            f = getattr(self._click, name)
            f = self._wrappers.get(name, lambda x: x)(f)
            self._cache[name] = f

        return self._cache[name]


_ui_lock = threading.Lock()


def _ui_function(f):
    @functools.wraps(f)
    def inner(*a, **kw):
        with _ui_lock:
            rv = f(*a, **kw)
        return rv
    return inner


class _Stack(object):
    def __init__(self):
        self._stack = []

    @property
    def top(self):
        return self._stack[-1]

    def push(self, value):
        self._stack.append(value)

    def pop(self):
        return self._stack.pop()


class _StackProxy(object):
    def __init__(self, stack):
        object.__setattr__(self, '_doubleclick_stack', stack)

    def __bool__(self):
        try:
            self._doubleclick_stack.top
        except IndexError:
            return False
        else:
            return True

    __nonzero__ = __bool__

    __getattr__ = lambda s, n: getattr(s._doubleclick_stack.top, n)
    __setattr__ = lambda s, n, v: setattr(s._doubleclick_stack.top, n, v)


_ctx_stack = _Stack()
ctx = _StackProxy(_ctx_stack)


def _ctx_pushing_class(cls):
    class ContextPusher(cls):
        def command(self, *args, **kwargs):
            # Also wrap commands created with @group.command()
            def decorator(f):
                cmd = click.command(*args, **kwargs)(f)
                self.add_command(cmd)
                return cmd
            return decorator

        def invoke(self, ctx):
            _ctx_stack.push(ctx)
            try:
                cls.invoke(self, ctx)
            finally:
                new_ctx = _ctx_stack.pop()
                if new_ctx is not ctx:
                    raise RuntimeError(
                        'While doubleclick is supposed to make writing '
                        'threaded applications easier, it removes thread '
                        'safety from click. It is therefore not recommended '
                        'to launch more than one doubleclick application per '
                        'process.'
                    )

    return ContextPusher


def _command_class_wrapper(cls_name):
    def inner(f):
        def wrapper(name=None, **attrs):
            attrs.setdefault('cls', getattr(click, cls_name))
            return f(name, **attrs)
        return wrapper
    return inner


WRAPPERS = {
    'echo': _ui_function,
    'echo_via_pager': _ui_function,
    'prompt': _ui_function,
    'confirm': _ui_function,
    'clear': _ui_function,
    'edit': _ui_function,
    'launch': _ui_function,
    'getchar': _ui_function,
    'pause': _ui_function,
    'BaseCommand': _ctx_pushing_class,
    'Command': _ctx_pushing_class,
    'MultiCommand': _ctx_pushing_class,
    'Group': _ctx_pushing_class,
    'CommandCollection': _ctx_pushing_class,
    'command': _command_class_wrapper('Command'),
    'group': _command_class_wrapper('Group')
}

click = _ClickProxy(WRAPPERS)
