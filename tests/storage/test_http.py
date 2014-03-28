# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.test_http
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from .. import assert_item_equals
from textwrap import dedent
from vdirsyncer.storage.http import HttpStorage, Item
from requests import Response


class TestHttpStorage(object):

    def test_list(self, monkeypatch):
        collection_url = 'http://127.0.0.1/calendar/collection/'

        responses = [
            dedent(b'''
                    BEGIN:VCALENDAR
                    VERSION:2.0
                    PRODID:http://www.example.com/calendarapplication/
                    METHOD:PUBLISH
                    BEGIN:VEVENT
                    UID:461092315540@example.com
                    LOCATION:Somewhere
                    SUMMARY:Eine Kurzinfo
                    DESCRIPTION:Beschreibung des Termines
                    CLASS:PUBLIC
                    DTSTART:20060910T220000Z
                    DTEND:20060919T215900Z
                    DTSTAMP:20060812T125900Z
                    END:VEVENT
                    BEGIN:VEVENT
                    UID:461092315asdasd540@example.com
                    LOCATION:Somewhere else
                    SUMMARY:Eine zweite Kurzinfo
                    DESCRIPTION:Beschreibung des anderen Termines
                    BEGIN:VALARM
                    ACTION:AUDIO
                    TRIGGER:19980403T120000
                    ATTACH;FMTTYPE=audio/basic:http://host.com/pub/ssbanner.aud
                    REPEAT:4
                    DURATION:PT1H
                    END:VALARM
                    END:VEVENT
                    END:VCALENDAR
                ''')
        ]

        def get(*a, **kw):
            r = Response()
            r.status_code = 200
            assert responses
            r._content = responses.pop()
            return r

        monkeypatch.setattr('requests.get', get)

        s = HttpStorage(url=collection_url)
        l = list(s.list())

        hrefs = set(href for href, etag in l)
        href1 = u'461092315540@example.com'
        href2 = u'461092315asdasd540@example.com'
        assert hrefs == set((href1, href2))

        item, etag = s.get(href1)
        assert_item_equals(item, Item(dedent(u'''
            BEGIN:VEVENT
            UID:461092315540@example.com
            LOCATION:Somewhere
            SUMMARY:Eine Kurzinfo
            DESCRIPTION:Beschreibung des Termines
            CLASS:PUBLIC
            DTSTART:20060910T220000Z
            DTEND:20060919T215900Z
            DTSTAMP:20060812T125900Z
            END:VEVENT
        ''').strip()))

        item, etag = s.get(href2)
        assert_item_equals(item, Item(dedent(u'''
            BEGIN:VEVENT
            UID:461092315asdasd540@example.com
            LOCATION:Somewhere else
            SUMMARY:Eine zweite Kurzinfo
            DESCRIPTION:Beschreibung des anderen Termines
            BEGIN:VALARM
            ACTION:AUDIO
            TRIGGER:19980403T120000
            ATTACH;FMTTYPE=audio/basic:http://host.com/pub/ssbanner.aud
            REPEAT:4
            DURATION:PT1H
            END:VALARM
            END:VEVENT
        ''').strip()))
