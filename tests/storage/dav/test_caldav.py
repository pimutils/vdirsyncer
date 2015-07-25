# -*- coding: utf-8 -*-

import datetime
from textwrap import dedent

import pytest

import requests
import requests.exceptions

from tests import EVENT_TEMPLATE, TASK_TEMPLATE, VCARD_TEMPLATE

from vdirsyncer import exceptions
from vdirsyncer.storage.dav import CaldavStorage

from . import DavStorageTests, dav_server
from .. import format_item


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
