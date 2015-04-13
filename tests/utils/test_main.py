# -*- coding: utf-8 -*-

import os
import platform
import stat

import click
from click.testing import CliRunner

import pytest

import requests

from vdirsyncer import doubleclick, utils

# These modules might be uninitialized and unavailable if not explicitly
# imported
import vdirsyncer.utils.compat  # noqa
import vdirsyncer.utils.http  # noqa
import vdirsyncer.utils.password  # noqa


from .. import blow_up


class EmptyNetrc(object):
    def __init__(self, file=None):
        self._file = file

    def authenticators(self, hostname):
        return None


class EmptyKeyring(object):
    def get_password(self, *a, **kw):
        return None


@pytest.fixture(autouse=True)
def empty_password_storages(monkeypatch):
    monkeypatch.setattr('netrc.netrc', EmptyNetrc)
    monkeypatch.setattr(utils.password, 'keyring', EmptyKeyring())


def test_get_password_from_netrc(monkeypatch):
    username = 'foouser'
    password = 'foopass'
    resource = 'http://example.com/path/to/whatever/'
    hostname = 'example.com'

    calls = []

    class Netrc(object):
        def authenticators(self, hostname):
            calls.append(hostname)
            return username, 'bogus', password

    monkeypatch.setattr('netrc.netrc', Netrc)
    monkeypatch.setattr('getpass.getpass', blow_up)

    _password = utils.password.get_password(username, resource)
    assert _password == password
    assert calls == [hostname]


def test_get_password_from_system_keyring(monkeypatch):
    username = 'foouser'
    password = 'foopass'
    resource = 'http://example.com/path/to/whatever/'
    hostname = 'example.com'

    class KeyringMock(object):
        def get_password(self, resource, _username):
            assert _username == username
            assert resource == utils.password.password_key_prefix + hostname
            return password

    monkeypatch.setattr(utils.password, 'keyring', KeyringMock())

    monkeypatch.setattr('getpass.getpass', blow_up)

    _password = utils.password.get_password(username, resource)
    assert _password == password


def test_get_password_from_command(tmpdir):
    username = 'my_username'
    resource = 'http://example.com'
    password = 'testpassword'
    filename = 'command.sh'

    filepath = str(tmpdir) + '/' + filename
    f = open(filepath, 'w')
    f.write('#!/bin/sh\n'
            '[ "$1" != "my_username" ] && exit 1\n'
            '[ "$2" != "example.com" ] && exit 1\n'
            'echo "{}"'.format(password))
    f.close()

    st = os.stat(filepath)
    os.chmod(filepath, st.st_mode | stat.S_IEXEC)

    @doubleclick.click.command()
    @doubleclick.click.pass_context
    def fake_app(ctx):
        ctx.obj = {'config': ({'password_command': filepath}, {}, {})}
        _password = utils.password.get_password(username, resource)
        assert _password == password

    runner = CliRunner()
    result = runner.invoke(fake_app)
    assert not result.exception


def test_get_password_from_prompt():
    user = 'my_user'
    resource = 'http://example.com'

    @click.command()
    def fake_app():
        x = utils.password.get_password(user, resource)
        click.echo('Password is {}'.format(x))

    runner = CliRunner()
    result = runner.invoke(fake_app, input='my_password\n\n')
    assert not result.exception
    assert result.output.splitlines() == [
        'Server password for {} at host {}: '.format(user, 'example.com'),
        'Password is my_password'
    ]


def test_set_keyring_password(monkeypatch):
    class KeyringMock(object):
        def get_password(self, resource, username):
            assert resource == \
                utils.password.password_key_prefix + 'example.com'
            assert username == 'foouser'
            return None

        def set_password(self, resource, username, password):
            assert resource == \
                utils.password.password_key_prefix + 'example.com'
            assert username == 'foouser'
            assert password == 'hunter2'

    monkeypatch.setattr(utils.password, 'keyring', KeyringMock())

    @doubleclick.click.command()
    @doubleclick.click.pass_context
    def fake_app(ctx):
        ctx.obj = {}
        x = utils.password.get_password('foouser', 'http://example.com/a/b')
        click.echo('password is ' + x)

    runner = CliRunner()
    result = runner.invoke(fake_app, input='hunter2\ny\n')
    assert not result.exception
    assert result.output == (
        'Server password for foouser at host example.com: \n'
        'Save this password in the keyring? [y/N]: y\n'
        'password is hunter2\n'
    )


def test_get_password_from_cache(monkeypatch):
    user = 'my_user'
    resource = 'http://example.com'

    @doubleclick.click.command()
    @doubleclick.click.pass_context
    def fake_app(ctx):
        ctx.obj = {}
        x = utils.password.get_password(user, resource)
        click.echo('Password is {}'.format(x))
        monkeypatch.setattr(doubleclick.click, 'prompt', blow_up)

        assert (user, 'example.com') in ctx.obj['passwords']
        x = utils.password.get_password(user, resource)
        click.echo('Password is {}'.format(x))

    runner = CliRunner()
    result = runner.invoke(fake_app, input='my_password\n')
    assert not result.exception
    assert result.output.splitlines() == [
        'Server password for {} at host {}: '.format(user, 'example.com'),
        'Save this password in the keyring? [y/N]: ',
        'Password is my_password',
        'debug: Got password for my_user from internal cache',
        'Password is my_password'
    ]


def test_get_class_init_args():
    class Foobar(object):
        def __init__(self, foo, bar, baz=None):
            pass

    all, required = utils.get_class_init_args(Foobar)
    assert all == {'foo', 'bar', 'baz'}
    assert required == {'foo', 'bar'}


def test_get_class_init_args_on_storage():
    from vdirsyncer.storage.memory import MemoryStorage

    all, required = utils.get_class_init_args(MemoryStorage)
    assert all == set(['fileext', 'collection', 'read_only', 'instance_name',
                       'collection_human'])
    assert not required


@pytest.mark.skipif((not utils.compat.PY2
                     or platform.python_implementation() == 'PyPy'),
                    reason='https://github.com/shazow/urllib3/issues/529')
def test_request_ssl(httpsserver):
    sha1 = '94:FD:7A:CB:50:75:A4:69:82:0A:F8:23:DF:07:FC:69:3E:CD:90:CA'
    md5 = '19:90:F7:23:94:F2:EF:AB:2B:64:2D:57:3D:25:95:2D'

    httpsserver.serve_content('')  # we need to serve something

    with pytest.raises(requests.exceptions.SSLError) as excinfo:
        utils.http.request('GET', httpsserver.url)
    assert 'certificate verify failed' in str(excinfo.value)
    utils.http.request('GET', httpsserver.url, verify=False)
    utils.http.request('GET', httpsserver.url,
                       verify_fingerprint=sha1)
    utils.http.request('GET', httpsserver.url, verify_fingerprint=md5)
    with pytest.raises(requests.exceptions.SSLError) as excinfo:
        utils.http.request('GET', httpsserver.url,
                           verify_fingerprint=''.join(reversed(sha1)))
    assert 'Fingerprints did not match' in str(excinfo.value)
