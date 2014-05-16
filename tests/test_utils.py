# -*- coding: utf-8 -*-
'''
    tests.test_utils
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import pytest
import vdirsyncer.utils as utils
from vdirsyncer.utils.vobject import split_collection

from . import normalize_item, SIMPLE_TEMPLATE, BARE_EVENT_TEMPLATE


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


def test_split_collection_simple():
    input = u'\r\n'.join((
        u'BEGIN:VADDRESSBOOK',
        SIMPLE_TEMPLATE.format(r=123),
        SIMPLE_TEMPLATE.format(r=345),
        SIMPLE_TEMPLATE.format(r=678),
        u'END:VADDRESSBOOK'
    ))

    given = split_collection(input)
    expected = [
        SIMPLE_TEMPLATE.format(r=123),
        SIMPLE_TEMPLATE.format(r=345),
        SIMPLE_TEMPLATE.format(r=678)
    ]

    assert set(normalize_item(item) for item in given) == \
        set(normalize_item(item) for item in expected)


def test_split_collection_timezones():
    items = [
        BARE_EVENT_TEMPLATE.format(r=123),
        BARE_EVENT_TEMPLATE.format(r=345)
    ]

    timezone = (
        u'BEGIN:VTIMEZONE\r\n'
        u'TZID:/mozilla.org/20070129_1/Asia/Tokyo\r\n'
        u'X-LIC-LOCATION:Asia/Tokyo\r\n'
        u'BEGIN:STANDARD\r\n'
        u'TZOFFSETFROM:+0900\r\n'
        u'TZOFFSETTO:+0900\r\n'
        u'TZNAME:JST\r\n'
        u'DTSTART:19700101T000000\r\n'
        u'END:STANDARD\r\n'
        u'END:VTIMEZONE'
    )

    full = u'\r\n'.join(
        [u'BEGIN:VCALENDAR'] +
        items +
        [timezone, u'END:VCALENDAR']
    )

    given = set(normalize_item(item) for item in split_collection(full))
    expected = set(
        normalize_item(u'\r\n'.join((
            u'BEGIN:VCALENDAR', item, timezone, u'END:VCALENDAR'
        )))
        for item in items
    )

    assert given == expected


