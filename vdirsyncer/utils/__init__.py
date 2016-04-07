# -*- coding: utf-8 -*-

import functools
import os
import sys
import uuid

from .compat import getargspec_ish, iteritems, to_unicode
from .. import exceptions


SAFE_UID_CHARS = ('abcdefghijklmnopqrstuvwxyz'
                  'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                  '0123456789_.-+')


_missing = object()


def expand_path(p):
    p = os.path.expanduser(p)
    p = os.path.normpath(p)
    return p


def split_dict(d, f):
    '''Puts key into first dict if f(key), otherwise in second dict'''
    a, b = split_sequence(iteritems(d), lambda item: f(item[0]))
    return dict(a), dict(b)


def split_sequence(s, f):
    '''Puts item into first list if f(item), else in second list'''
    a = []
    b = []
    for item in s:
        if f(item):
            a.append(item)
        else:
            b.append(item)

    return a, b


def uniq(s):
    '''Filter duplicates while preserving order. ``set`` can almost always be
    used instead of this, but preserving order might prove useful for
    debugging.'''
    d = set()
    for x in s:
        if x not in d:
            d.add(x)
            yield x


def get_etag_from_file(fpath):
    '''Get mtime-based etag from a filepath.'''
    stat = os.stat(fpath)
    mtime = getattr(stat, 'st_mtime_ns', None)
    if mtime is None:
        mtime = stat.st_mtime
    return '{:.9f}'.format(mtime)


def get_etag_from_fileobject(f):
    '''
    Get mtime-based etag from a local file's fileobject.

    This function will flush/sync the file as much as necessary to obtain a
    correct mtime.

    In filesystem-based storages, this is used instead of
    :py:func:`get_etag_from_file` to determine the correct etag *before*
    writing the temporary file to the target location.

    This works because, as far as I've tested, moving and linking a file
    doesn't change its mtime.
    '''
    f.flush()  # Only this is necessary on Linux
    if sys.platform == 'win32':
        os.fsync(f.fileno())  # Apparently necessary on Windows
    return get_etag_from_file(f.name)


def get_storage_init_specs(cls, stop_at=object):
    if cls is stop_at:
        return ()

    spec = getargspec_ish(cls.__init__)
    traverse_superclass = getattr(cls.__init__, '_traverse_superclass', True)
    if traverse_superclass:
        if traverse_superclass is True:  # noqa
            supercls = next(getattr(x.__init__, '__objclass__', x)
                            for x in cls.__mro__[1:])
        else:
            supercls = traverse_superclass
        superspecs = get_storage_init_specs(supercls, stop_at=stop_at)
    else:
        superspecs = ()

    return (spec,) + superspecs


def get_storage_init_args(cls, stop_at=object):
    '''
    Get args which are taken during class initialization. Assumes that all
    classes' __init__ calls super().__init__ with the rest of the arguments.

    :param cls: The class to inspect.
    :returns: (all, required), where ``all`` is a set of all arguments the
        class can take, and ``required`` is the subset of arguments the class
        requires.
    '''
    all, required = set(), set()
    for spec in get_storage_init_specs(cls, stop_at=stop_at):
        all.update(spec.args[1:])
        last = -len(spec.defaults) if spec.defaults else len(spec.args)
        required.update(spec.args[1:last])

    return all, required


def checkdir(path, create=False, mode=0o750):
    '''
    Check whether ``path`` is a directory.

    :param create: Whether to create the directory (and all parent directories)
        if it does not exist.
    :param mode: Mode to create missing directories with.
    '''

    if not os.path.isdir(path):
        if os.path.exists(path):
            raise IOError('{} is not a directory.'.format(path))
        if create:
            os.makedirs(path, mode)
        else:
            raise exceptions.CollectionNotFound('Directory {} does not exist.'
                                                .format(path))


def checkfile(path, create=False):
    '''
    Check whether ``path`` is a file.

    :param create: Whether to create the file's parent directories if they do
        not exist.
    '''
    checkdir(os.path.dirname(path), create=create)
    if not os.path.isfile(path):
        if os.path.exists(path):
            raise IOError('{} is not a file.'.format(path))
        if create:
            with open(path, 'wb'):
                pass
        else:
            raise exceptions.CollectionNotFound('File {} does not exist.'
                                                .format(path))


class cached_property(object):
    '''A read-only @property that is only evaluated once. Only usable on class
    instances' methods.
    '''
    def __init__(self, fget, doc=None):
        self.__name__ = fget.__name__
        self.__module__ = fget.__module__
        self.__doc__ = doc or fget.__doc__
        self.fget = fget

    def __get__(self, obj, cls):
        if obj is None:  # pragma: no cover
            return self
        obj.__dict__[self.__name__] = result = self.fget(obj)
        return result


def href_safe(ident, safe=SAFE_UID_CHARS):
    return not bool(set(ident) - set(safe))


def generate_href(ident=None, safe=SAFE_UID_CHARS):
    '''
    Generate a safe identifier, suitable for URLs, storage hrefs or UIDs.

    If the given ident string is safe, it will be returned, otherwise a random
    UUID.
    '''
    if not ident or not href_safe(ident, safe):
        return to_unicode(uuid.uuid4().hex)
    else:
        return ident


def synchronized(lock=None):
    if lock is None:
        from threading import Lock
        lock = Lock()

    def inner(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            with lock:
                return f(*args, **kwargs)
        return wrapper
    return inner


def open_graphical_browser(url, new=0, autoraise=True):
    '''Open a graphical web browser.

    This is basically like `webbrowser.open`, but without trying to launch CLI
    browsers at all. We're excluding those since it's undesirable to launch
    those when you're using vdirsyncer on a server. Rather copypaste the URL
    into the local browser, or use the URL-yanking features of your terminal
    emulator.
    '''
    import webbrowser
    cli_names = set(['www-browser', 'links', 'links2', 'elinks', 'lynx',
                     'w3m'])

    for name in webbrowser._tryorder:
        if name in cli_names:
            continue

        browser = webbrowser.get(name)
        if browser.open(url, new, autoraise):
            return

    raise RuntimeError('No graphical browser found. Please open the URL '
                       'manually.')
