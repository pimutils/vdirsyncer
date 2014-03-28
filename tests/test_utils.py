# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.test_utils
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import pytest
import vdirsyncer.utils as utils


def test_parse_options():
    o = {
        'foo': 'yes',
        'bar': '',
        'baz': 'whatever',
        'bam': '123',
        'asd': 'off'
    }

    assert dict(utils.parse_options(o.items())) == {
        'foo': True,
        'bar': '',
        'baz': 'whatever',
        'bam': 123,
        'asd': False
    }


def test_get_password_from_netrc(monkeypatch):
    username = 'foouser'
    password = 'foopass'
    resource = 'http://example.com/path/to/whatever/'
    hostname = 'example.com'

    calls = []

    def authenticators(self, hostname):
        calls.append(hostname)
        return username, 'bogus', password

    import netrc

    monkeypatch.setattr(netrc.netrc, 'authenticators', authenticators)

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

    import sys
    monkeypatch.setitem(sys.modules, 'keyring', KeyringMock())

    import netrc
    netrc_calls = []

    def authenticators(self, h):
        netrc_calls.append(h)
        return None

    monkeypatch.setattr(netrc.netrc, 'authenticators', authenticators)

    _password = utils.get_password(username, resource)
    assert _password == password
    assert netrc_calls == [hostname]
