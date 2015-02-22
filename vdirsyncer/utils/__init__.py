# -*- coding: utf-8 -*-

import os
import sys
import threading

import requests
from requests.packages.urllib3.poolmanager import PoolManager

from .compat import iteritems, urlparse
from .. import exceptions, log
from ..doubleclick import click, ctx


logger = log.get(__name__)
_missing = object()


try:
    import keyring
except ImportError:
    keyring = None


password_key_prefix = 'vdirsyncer:'


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


def get_password(username, resource, _lock=threading.Lock()):
    """tries to access saved password or asks user for it

    will try the following in this order:
        1. read password from netrc (and only the password, username
           in netrc will be ignored)
        2. read password from keyring (keyring needs to be installed)
        3. read password from the command passed as password_command in the
           general config section with username and host as parameters
        4a ask user for the password
         b save in keyring if installed and user agrees

    :param username: user's name on the server
    :type username: str/unicode
    :param resource: a resource to which the user has access via password,
                     it will be shortened to just the hostname. It is assumed
                     that each unique username/hostname combination only ever
                     uses the same password.
    :type resource: str/unicode
    :return: password
    :rtype: str/unicode


    """
    if ctx:
        password_cache = ctx.obj.setdefault('passwords', {})

    with _lock:
        host = urlparse.urlsplit(resource).hostname
        for func in (_password_from_command, _password_from_cache,
                     _password_from_netrc, _password_from_keyring):
            password = func(username, host)
            if password is not None:
                logger.debug('Got password for {} from {}'
                             .format(username, func.__doc__))
                return password

        prompt = ('Server password for {} at host {}'.format(username, host))
        password = click.prompt(prompt, hide_input=True)

        if ctx and func is not _password_from_cache:
            password_cache[(username, host)] = password
            if keyring is not None and \
               click.confirm('Save this password in the keyring?',
                             default=False):
                keyring.set_password(password_key_prefix + host,
                                     username, password)

        return password


def _password_from_cache(username, host):
    '''internal cache'''
    if ctx:
        return ctx.obj['passwords'].get((username, host), None)


def _password_from_netrc(username, host):
    '''.netrc'''
    from netrc import netrc

    try:
        netrc_user, account, password = \
            netrc().authenticators(host) or (None, None, None)
        if netrc_user == username:
            return password
    except IOError:
        pass


def _password_from_keyring(username, host):
    '''system keyring'''
    if keyring is None:
        return None

    return keyring.get_password(password_key_prefix + host, username)


def _password_from_command(username, host):
    '''command'''
    import subprocess

    if not ctx:
        return None

    try:
        general, _, _ = ctx.obj['config']
        command = general['password_command'].split()
    except KeyError:
        return None

    if not command:
        return None

    command[0] = expand_path(command[0])

    try:
        stdout = subprocess.check_output(command + [username, host],
                                         universal_newlines=True)
        return stdout.strip()
    except OSError as e:
        logger.warning('Failed to execute command: {}\n{}'.
                       format(' '.join(command), str(e)))


class _FingerprintAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, fingerprint=None, **kwargs):
        self.fingerprint = str(fingerprint)
        super(_FingerprintAdapter, self).__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       assert_fingerprint=self.fingerprint)


def _verify_fingerprint_works():
    try:
        import requests
        from pkg_resources import parse_version as ver

        return ver(requests.__version__) >= ver('2.4.1')
    except Exception:
        return False

# https://github.com/shazow/urllib3/pull/444
# We check this here instead of setup.py, because:
# - This is critical to security of `verify_fingerprint`, and Python's
#   packaging stuff doesn't check installed versions.
# - The people who don't use `verify_fingerprint` wouldn't care.
VERIFY_FINGERPRINT_WORKS = _verify_fingerprint_works()
del _verify_fingerprint_works


def request(method, url, session=None, latin1_fallback=True,
            verify_fingerprint=None, **kwargs):
    '''
    Wrapper method for requests, to ease logging and mocking. Parameters should
    be the same as for ``requests.request``, except:

    :param session: A requests session object to use.
    :param verify_fingerprint: Optional. SHA1 or MD5 fingerprint of the
        expected server certificate.
    :param latin1_fallback: RFC-2616 specifies the default Content-Type of
        text/* to be latin1, which is not always correct, but exactly what
        requests is doing. Setting this parameter to False will use charset
        autodetection (usually ending up with utf8) instead of plainly falling
        back to this silly default. See
        https://github.com/kennethreitz/requests/issues/2042
    '''

    if session is None:
        session = requests.Session()

    if verify_fingerprint is not None:
        if not VERIFY_FINGERPRINT_WORKS:
            raise ValueError('`verify_fingerprint` can only be used with '
                             'requests versions >= 2.4.1')
        kwargs['verify'] = False
        https_prefix = 'https://'

        if not isinstance(session.adapters[https_prefix], _FingerprintAdapter):
            fingerprint_adapter = _FingerprintAdapter(verify_fingerprint)
            session.mount(https_prefix, fingerprint_adapter)

    func = session.request

    logger.debug(u'{} {}'.format(method, url))
    logger.debug(kwargs.get('headers', {}))
    logger.debug(kwargs.get('data', None))
    logger.debug('Sending request...')
    r = func(method, url, **kwargs)

    # See https://github.com/kennethreitz/requests/issues/2042
    content_type = r.headers.get('Content-Type', '')
    if not latin1_fallback and \
       'charset' not in content_type and \
       content_type.startswith('text/'):
        logger.debug('Removing latin1 fallback')
        r.encoding = None

    logger.debug(r.status_code)
    logger.debug(r.headers)
    logger.debug(r.content)

    if r.status_code == 412:
        raise exceptions.PreconditionFailed(r.reason)
    if r.status_code == 404:
        raise exceptions.NotFoundError(r.reason)

    r.raise_for_status()
    return r


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


def get_class_init_specs(cls, stop_at=object):
    if cls is stop_at:
        return ()
    import inspect
    spec = inspect.getargspec(cls.__init__)
    supercls = next(getattr(x.__init__, '__objclass__', x)
                    for x in cls.__mro__[1:])
    return (spec,) + get_class_init_specs(supercls, stop_at=stop_at)


def get_class_init_args(cls, stop_at=object):
    '''
    Get args which are taken during class initialization. Assumes that all
    classes' __init__ calls super().__init__ with the rest of the arguments.

    :param cls: The class to inspect.
    :returns: (all, required), where ``all`` is a set of all arguments the
        class can take, and ``required`` is the subset of arguments the class
        requires.
    '''
    all, required = set(), set()
    for spec in get_class_init_specs(cls, stop_at=stop_at):
        all.update(spec.args[1:])
        required.update(spec.args[1:-len(spec.defaults or ())])

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
    '''
    Copied from Werkzeug.
    Copyright 2007-2014 Armin Ronacher
    '''

    def __init__(self, func, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, _missing)
        if value is _missing:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value
