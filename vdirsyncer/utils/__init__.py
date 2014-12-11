# -*- coding: utf-8 -*-
'''
    vdirsyncer.utils
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import json
import os
import threading

import requests
from requests.packages.urllib3.poolmanager import PoolManager

from .compat import iteritems, text_type, urlparse
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
    p = os.path.abspath(p)
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
    d = set()
    for x in s:
        if x not in d:
            d.add(x)
            yield x


def parse_config_value(value):
    try:
        return json.loads(value)
    except ValueError:
        rv = value

    if value.lower() in ('on', 'true', 'yes'):
        logger.warning('{} is deprecated for the config, please use true.\n'
                       'The old form will be removed in 0.4.0.'
                       .format(value))
        return True
    if value.lower() in ('off', 'false', 'no'):
        logger.warning('{} is deprecated for the config, please use false.\n'
                       'The old form will be removed in 0.4.0.'
                       .format(value))
        return False
    if value.lower() == 'none':
        logger.warning('None is deprecated for the config, please use null.\n'
                       'The old form will be removed in 0.4.0.')
        return None

    if '#' in value:
        raise ValueError('Invalid value:{}\n'
                         'Use double quotes (") if you want to use hashes in '
                         'your value.')

    if len(value.splitlines()) > 1:
        # ConfigParser's barrier for mistaking an arbitrary line for the
        # continuation of a value is awfully low. The following example will
        # also contain the second line in the value:
        #
        # foo = bar
        #  # my comment
        raise ValueError('No multiline-values allowed:\n{!r}'.format(value))

    return rv


def parse_options(items, section=None):
    for key, value in items:
        try:
            yield key, parse_config_value(value)
        except ValueError as e:
            raise ValueError('Section {!r}, option {!r}: {}'
                             .format(section, key, e))


def get_password(username, resource, _lock=threading.Lock()):
    """tries to access saved password or asks user for it

    will try the following in this order:
        1. read password from netrc (and only the password, username
           in netrc will be ignored)
        2. read password from keyring (keyring needs to be installed)
        3. read password from the command passed as passwordeval in the
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
        command = general['passwordeval'].split()
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


def request(method, url, data=None, headers=None, auth=None, verify=None,
            session=None, latin1_fallback=True, verify_fingerprint=None):
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
        https_prefix = 'https://'

        if not isinstance(session.adapters[https_prefix], _FingerprintAdapter):
            fingerprint_adapter = _FingerprintAdapter(verify_fingerprint)
            session.mount(https_prefix, fingerprint_adapter)

    func = session.request

    logger.debug(u'{} {}'.format(method, url))
    logger.debug(headers)
    logger.debug(data)
    logger.debug('Sending request...')
    r = func(method, url, data=data, headers=headers, auth=auth, verify=verify)

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


class safe_write(object):
    '''A helper class for performing atomic writes.  Writes to a tempfile in
    the same directory and then renames. The tempfile location can be
    overridden, but must reside on the same filesystem to be atomic.

    Usage::

        with safe_write(fpath, 'w+') as f:
            f.write('hohoho')
    '''

    f = None
    tmppath = None
    fpath = None
    mode = None

    def __init__(self, fpath, mode, tmppath=None):
        self.tmppath = tmppath or fpath + '.tmp'
        self.fpath = fpath
        self.mode = mode

    def __enter__(self):
        self.f = f = open(self.tmppath, self.mode)
        self.write = f.write
        return self

    def __exit__(self, cls, value, tb):
        self.f.close()
        if cls is None:
            os.rename(self.tmppath, self.fpath)
        else:
            os.remove(self.tmppath)

    def get_etag(self):
        self.f.flush()
        return get_etag_from_file(self.tmppath)


def get_etag_from_file(fpath):
    return '{:.9f}'.format(os.path.getmtime(fpath))


def get_class_init_args(cls):
    '''
    Get args which are taken during class initialization. Assumes that all
    classes' __init__ calls super().__init__ with the rest of the arguments.

    :param cls: The class to inspect.
    :returns: (all, required), where ``all`` is a set of all arguments the
        class can take, and ``required`` is the subset of arguments the class
        requires.
    '''
    import inspect

    if cls is object:
        return set(), set()

    spec = inspect.getargspec(cls.__init__)
    all = set(spec.args[1:])
    required = set(spec.args[1:-len(spec.defaults or ())])
    supercls = next(getattr(x.__init__, '__objclass__', x)
                    for x in cls.__mro__[1:])
    s_all, s_required = get_class_init_args(supercls)

    return all | s_all, required | s_required


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
            raise IOError('Directory {} does not exist. Use create = '
                          'True in your configuration to automatically '
                          'create it, or create it '
                          'yourself.'.format(path))


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
        if not create:
            raise IOError('File {} does not exist. Use create = '
                          'True in your configuration to automatically '
                          'create it, or create it '
                          'yourself.'.format(path))


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
