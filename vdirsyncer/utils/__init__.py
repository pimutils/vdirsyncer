# -*- coding: utf-8 -*-
'''
    vdirsyncer.utils
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import os

import click

import requests

from .. import exceptions, log
from .compat import iteritems, urlparse


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


def parse_options(items, section=None):
    for key, value in items:
        if len(value.splitlines()) > 1:
            # The reason we use comma-separated values instead of
            # multiline-values for lists is simple: ConfigParser's barrier for
            # mistaking an arbitrary line for the continuation of a value is
            # awfully low.
            #
            # Take this example:
            #
            # foo = bar
            #  # my comment
            #
            # For reasons beyond my understanding ConfigParser only requires
            # one space to interpret the line as part of a multiline-value.
            # Related to that, it also parses any inline-comments as value:
            #
            # foo = bar  # this comment is part of the value!
            raise ValueError('Section {!r}, option {!r}: '
                             'No multiline-values allowed.'
                             .format(section, key))

        if value.lower() in ('yes', 'true', 'on'):
            value = True
        elif value.lower() in ('no', 'false', 'off'):
            value = False
        else:
            try:
                value = int(value)
            except ValueError:
                pass
        yield key, value


def _password_from_netrc(username, resource):
    '''.netrc'''
    from netrc import netrc

    hostname = urlparse.urlsplit(resource).hostname
    try:
        netrc_user, account, password = \
            netrc().authenticators(hostname) or (None, None, None)
        if netrc_user == username:
            return password
    except IOError:
        pass


def _password_from_keyring(username, resource):
    '''system keyring'''
    if keyring is None:
        return None

    key = resource
    password = None

    while True:
        password = keyring.get_password(password_key_prefix + key, username)
        if password is not None:
            return password

        parsed = urlparse.urlsplit(key)
        path = parsed.path
        if not path:
            return None
        elif path.endswith('/'):
            path = path.rstrip('/')
        else:
            path = path.rsplit('/', 1)[0] + '/'

        new_key = urlparse.urlunsplit((
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.query,
            parsed.fragment
        ))
        if new_key == key:
            return None
        key = new_key


def get_password(username, resource):
    """tries to access saved password or asks user for it

    will try the following in this order:
        1. read password from netrc (and only the password, username
           in netrc will be ignored)
        2. read password from keyring (keyring needs to be installed)
        3a ask user for the password
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
    for func in (_password_from_netrc, _password_from_keyring):
        password = func(username, resource)
        if password is not None:
            logger.debug('Got password for {} from {}'
                         .format(username, func.__doc__))
            return password

    prompt = ('Server password for {} at the resource {}'
              .format(username, resource))
    password = click.prompt(prompt, hide_input=True)

    if keyring is not None and \
       click.confirm('Save this password in the keyring?', default=False):
        keyring.set_password(password_key_prefix + resource,
                             username, password)

    return password


def request(method, url, data=None, headers=None, auth=None, verify=None,
            session=None, latin1_fallback=True):
    '''wrapper method for requests, to ease logging and mocking'''

    if session is None:
        func = requests.request
    else:
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
    f = None
    tmppath = None
    fpath = None
    mode = None

    def __init__(self, fpath, mode):
        self.tmppath = fpath + '.tmp'
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


def checkdir(path, create=False):
    if not os.path.isdir(path):
        if os.path.exists(path):
            raise IOError('{} is not a directory.'.format(path))
        if create:
            os.makedirs(path, 0o750)
        else:
            raise IOError('Directory {} does not exist. Use create = '
                          'True in your configuration to automatically '
                          'create it, or create it '
                          'yourself.'.format(path))


def checkfile(path, create=False):
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
