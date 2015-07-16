# -*- coding: utf-8 -*-

import threading

from . import expand_path
from .compat import urlparse
from .. import exceptions, log
from ..doubleclick import click, ctx

logger = log.get(__name__)
password_key_prefix = 'vdirsyncer:'

try:
    import keyring
except ImportError:
    keyring = None


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
    else:
        password_cache = {}  # discard passwords

    def _password_from_cache(username, host):
        '''internal cache'''
        return password_cache.get((username, host), None)

    with _lock:
        host = urlparse.urlsplit(resource).hostname
        for func in (_password_from_cache, _password_from_command,
                     _password_from_netrc, _password_from_keyring,
                     _password_from_prompt):
            password = func(username, host)
            if password is not None:
                logger.debug('Got password for {} from {}'
                             .format(username, func.__doc__))
                break

        password_cache[(username, host)] = password
        return password


def _password_from_prompt(username, host):
    '''prompt'''
    prompt = ('Server password for {} at host {}'.format(username, host))
    password = click.prompt(prompt, hide_input=True)
    if keyring is not None and \
       click.confirm('Save this password in the keyring?',
                     default=False):
        keyring.set_password(password_key_prefix + host,
                             username, password)
    return password


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
        return stdout.strip('\n')
    except OSError as e:
        raise exceptions.UserError('Failed to execute command: {}\n{}'.
                                   format(' '.join(command), str(e)))
