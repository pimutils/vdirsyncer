# -*- coding: utf-8 -*-
'''
    tests.test_utils
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import pytest
import vdirsyncer.utils as utils


def test_parse_options():
    o = {
        'foo': 'yes',
        'hah': 'true',
        'bar': '',
        'baz': 'whatever',
        'bam': '123',
        'asd': 'off'
    }

    a = dict(utils.parse_options(o.items()))

    expected = {
        'foo': True,
        'hah': True,
        'bar': '',
        'baz': 'whatever',
        'bam': 123,
        'asd': False
    }

    assert a == expected

    for key in a:
        # Yes, we want a very strong typecheck here, because we actually have
        # to differentiate between bool and int, and in Python 2, bool is a
        # subclass of int.
        assert type(a[key]) is type(expected[key])  # flake8: noqa


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
    monkeypatch.setattr('getpass.getpass', None)

    _password = utils.get_password(username, resource)
    assert _password == password
    assert calls == [hostname]


@pytest.mark.parametrize('resources_to_test', range(1, 8))
def test_get_password_from_system_keyring(monkeypatch, resources_to_test):
    username = 'foouser'
    password = 'foopass'
    resource = 'http://example.com/path/to/whatever/'
    hostname = 'example.com'

    class KeyringMock(object):
        def __init__(self):
            p = utils.password_key_prefix
            self.resources = [
                p + 'http://example.com/path/to/whatever/',
                p + 'http://example.com/path/to/whatever',
                p + 'http://example.com/path/to/',
                p + 'http://example.com/path/to',
                p + 'http://example.com/path/',
                p + 'http://example.com/path',
                p + 'http://example.com/',
            ][:resources_to_test]

        def get_password(self, resource, _username):
            assert _username == username
            assert resource == self.resources.pop(0)
            if not self.resources:
                return password

    monkeypatch.setattr(utils, 'keyring', KeyringMock())

    netrc_calls = []

    class Netrc(object):
        def authenticators(self, hostname):
            netrc_calls.append(hostname)
            return None

    monkeypatch.setattr('netrc.netrc', Netrc)
    monkeypatch.setattr('getpass.getpass', None)

    _password = utils.get_password(username, resource)
    assert _password == password
    assert netrc_calls == [hostname]
