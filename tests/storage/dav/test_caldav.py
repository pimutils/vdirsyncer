# -*- coding: utf-8 -*-

import datetime
from textwrap import dedent

import pytest

from tests import EVENT_TEMPLATE, TASK_TEMPLATE, VCARD_TEMPLATE

from vdirsyncer.storage.dav import CalDAVStorage

from . import DAVStorageTests, dav_server
from .. import format_item


class TestCalDAVStorage(DAVStorageTests):
    storage_class = CalDAVStorage

    @pytest.fixture(params=['VTODO', 'VEVENT'])
    def item_type(self, request):
        return request.param

    def test_doesnt_accept_vcard(self, item_type, get_storage_args):
        s = self.storage_class(item_types=(item_type,), **get_storage_args())

        try:
            s.upload(format_item(item_template=VCARD_TEMPLATE))
        except Exception:
            pass
        assert not list(s.list())

    @pytest.mark.xfail(dav_server == 'radicale',
                       reason='Radicale doesn\'t support timeranges.')
    def test_timerange_correctness(self, get_storage_args):
        start_date = datetime.datetime(2013, 9, 10)
        end_date = datetime.datetime(2013, 9, 13)
        s = self.storage_class(start_date=start_date, end_date=end_date,
                               **get_storage_args())

        too_old_item = format_item(item_template=dedent(u'''
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

        too_new_item = format_item(item_template=dedent(u'''
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

        good_item = format_item(item_template=dedent(u'''
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
        expected_href, _ = s.upload(good_item)

        (actual_href, _), = s.list()
        assert actual_href == expected_href

    @pytest.mark.skipif(dav_server == 'icloud',
                        reason='iCloud only accepts VEVENT')
    def test_item_types_general(self, get_storage_args):
        args = get_storage_args()
        s = self.storage_class(**args)
        event = s.upload(format_item(item_template=EVENT_TEMPLATE))[0]
        task = s.upload(format_item(item_template=TASK_TEMPLATE))[0]

        for item_types, expected_items in [
            (('VTODO', 'VEVENT'), {event, task}),
            (('VTODO',), {task}),
            (('VEVENT',), {event}),
        ]:
            args['item_types'] = item_types
            s = self.storage_class(**args)
            assert set(href for href, etag in s.list()) == expected_items
