# -*- coding: utf-8 -*-
'''
    vdirsyncer.utils
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os

import vdirsyncer.log

def expand_path(p):
    p = os.path.expanduser(p)
    p = os.path.abspath(p)
    return p


def split_dict(d, f):
    a = {}
    b = {}
    for k, v in d.items():
        if f(k):
            a[k] = v
        else:
            b[k] = v

    return a, b


def parse_options(items):
    for key, value in items:
        if value.lower() in ('yes', 'true', 'on'):
            value = True
        elif value.lower() in ('no', 'false', 'off'):
            value = False
        try:
            value = int(value)
        except ValueError:
            pass
        yield key, value


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
    import getpass
    from netrc import netrc
    try:
        from urlparse import urlsplit
    except ImportError:
        from urllib.parse import urlsplit

    sync_logger = vdirsyncer.log.get('sync')

    # XXX is it save to asume that a password is always the same for
    # any given (hostname, username) combination?
    hostname = urlsplit(resource).hostname

    # netrc
    try:
        auths = netrc().authenticators(hostname)
        # auths = (user, password)
    except IOError:
        pass
    else:
        sync_logger.debug("Read password for user {0} on {1} in .netrc".format(
            auths[0], hostname))
        return auths[1]

    # keyring
    try:
        import keyring
    except ImportError:
        keyring, password = None, None
    else:
        password = keyring.get_password(
            'vdirsyncer:' + hostname, username)
        if password is not None:
            sync_logger.debug("Got password for user {0}@{1} from keyring".format(
                username, hostname))
            return password

    if password is None:
        prompt = 'Server password {0}@{1}: '.format(username, hostname)
        password = getpass.getpass(prompt=prompt)

    if keyring:
        answer = 'x'
        while answer.lower() not in ['', 'y', 'n']:
            prompt = 'Save this password in the keyring? [y/N] '
            answer = raw_input(prompt)
        if answer.lower() == 'y':
            password = keyring.set_password(
                'vdirsyncer:' + hostname, username, password)

    return password
