# -*- coding: utf-8 -*-

import datetime
import os
from textwrap import dedent

import pytest

import requests
import requests.exceptions

from tests import EVENT_TEMPLATE, TASK_TEMPLATE, VCARD_TEMPLATE, \
    assert_item_equals

import vdirsyncer.exceptions as exceptions
from vdirsyncer.storage.base import Item
from vdirsyncer.storage.dav import CaldavStorage, CarddavStorage, _parse_xml

from .. import StorageTests, format_item


dav_server = os.environ.get('DAV_SERVER', '').strip() or 'radicale'


def _get_server_mixin(server_name):
    from . import __name__ as base
    x = __import__('{}.servers.{}'.format(base, server_name), fromlist=[''])
    return x.ServerMixin

ServerMixin = _get_server_mixin(dav_server)


class DavStorageTests(ServerMixin, StorageTests):
    dav_server = dav_server

    def test_dav_broken_item(self, s):
        item = Item(u'HAHA:YES')
        try:
            s.upload(item)
        except (exceptions.Error, requests.exceptions.HTTPError):
            pass
        assert not list(s.list())

    def test_dav_empty_get_multi_performance(self, s, monkeypatch):
        def breakdown(*a, **kw):
            raise AssertionError('Expected not to be called.')

        monkeypatch.setattr('requests.sessions.Session.request', breakdown)

        assert list(s.get_multi([])) == []

    def test_dav_unicode_href(self, s, get_item, monkeypatch):
        if self.dav_server != 'radicale':
            # Radicale is unable to deal with unicode hrefs
            monkeypatch.setattr(s, '_get_href',
                                lambda item: item.ident + s.fileext)
        item = get_item(uid=u'lolätvdirsynceröü град сатану')
        href, etag = s.upload(item)
        item2, etag2 = s.get(href)
        assert_item_equals(item, item2)


class TestCaldavStorage(DavStorageTests):
    storage_class = CaldavStorage

    @pytest.fixture(params=['VTODO', 'VEVENT'])
    def item_type(self, request):
        return request.param

    def test_doesnt_accept_vcard(self, item_type, get_storage_args):
        s = self.storage_class(item_types=(item_type,), **get_storage_args())

        try:
            s.upload(format_item(VCARD_TEMPLATE))
        except (exceptions.Error, requests.exceptions.HTTPError):
            pass
        assert not list(s.list())

    # The `arg` param is not named `item_types` because that would hit
    # https://bitbucket.org/pytest-dev/pytest/issue/745/
    @pytest.mark.parametrize('arg,calls_num', [
        (('VTODO',), 1),
        (('VEVENT',), 1),
        (('VTODO', 'VEVENT'), 2),
        (('VTODO', 'VEVENT', 'VJOURNAL'), 3),
        ((), 1)
    ])
    def test_item_types_performance(self, get_storage_args, arg, calls_num,
                                    monkeypatch):
        s = self.storage_class(item_types=arg, **get_storage_args())
        old_parse = s._parse_prop_responses
        calls = []

        def new_parse(*a, **kw):
            calls.append(None)
            return old_parse(*a, **kw)

        monkeypatch.setattr(s, '_parse_prop_responses', new_parse)
        list(s.list())
        assert len(calls) == calls_num

    @pytest.mark.xfail(dav_server == 'radicale',
                       reason='Radicale doesn\'t support timeranges.')
    def test_timerange_correctness(self, get_storage_args):
        start_date = datetime.datetime(2013, 9, 10)
        end_date = datetime.datetime(2013, 9, 13)
        s = self.storage_class(start_date=start_date, end_date=end_date,
                               **get_storage_args())

        too_old_item = format_item(dedent(u'''
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:-//hacksw/handcal//NONSGML v1.0//EN
            BEGIN:VEVENT
            DTSTART:19970714T170000Z
            DTEND:19970715T035959Z
            SUMMARY:Bastille Day Party
            X-SOMETHING:{r}
            UID:{r}
            END:VEVENT
            END:VCALENDAR
            ''').strip())

        too_new_item = format_item(dedent(u'''
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:-//hacksw/handcal//NONSGML v1.0//EN
            BEGIN:VEVENT
            DTSTART:20150714T170000Z
            DTEND:20150715T035959Z
            SUMMARY:Another Bastille Day Party
            X-SOMETHING:{r}
            UID:{r}
            END:VEVENT
            END:VCALENDAR
            ''').strip())

        good_item = format_item(dedent(u'''
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:-//hacksw/handcal//NONSGML v1.0//EN
            BEGIN:VEVENT
            DTSTART:20130911T170000Z
            DTEND:20130912T035959Z
            SUMMARY:What's with all these Bastille Day Partys
            X-SOMETHING:{r}
            UID:{r}
            END:VEVENT
            END:VCALENDAR
            ''').strip())

        s.upload(too_old_item)
        s.upload(too_new_item)
        href, etag = s.upload(good_item)

        assert list(s.list()) == [(href, etag)]

    def test_invalid_resource(self, monkeypatch, get_storage_args):
        calls = []
        args = get_storage_args(collection=None)

        def request(session, method, url, **kwargs):
            assert url == args['url']
            calls.append(None)

            r = requests.Response()
            r.status_code = 200
            r._content = 'Hello World.'
            return r

        monkeypatch.setattr('requests.sessions.Session.request', request)

        with pytest.raises(ValueError):
            s = self.storage_class(**args)
            list(s.list())
        assert len(calls) == 1

    def test_item_types_general(self, s):
        event = s.upload(format_item(EVENT_TEMPLATE))
        task = s.upload(format_item(TASK_TEMPLATE))
        s.item_types = ('VTODO', 'VEVENT')
        assert set(s.list()) == set([event, task])
        s.item_types = ('VTODO',)
        assert set(s.list()) == set([task])
        s.item_types = ('VEVENT',)
        assert set(s.list()) == set([event])
        s.item_types = ()
        assert set(s.list()) == set([event, task])


class TestCarddavStorage(DavStorageTests):
    storage_class = CarddavStorage

    @pytest.fixture(params=['VCARD'])
    def item_type(self, request):
        return request.param


def test_broken_xml(capsys):
    rv = _parse_xml(b'<h1>\x10haha</h1>')
    assert rv.text == 'haha'
    warnings = capsys.readouterr()[1]
    assert 'partially invalid xml' in warnings.lower()
