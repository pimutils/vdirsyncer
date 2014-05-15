# -*- coding: utf-8 -*-
'''
    tests.storage.test_http
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from requests import Response

from tests import normalize_item, SIMPLE_TEMPLATE, BARE_EVENT_TEMPLATE
from vdirsyncer.storage.http import HttpStorage, split_collection


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


def test_list(monkeypatch):
    collection_url = 'http://127.0.0.1/calendar/collection.ics'

    items = [
        (u'BEGIN:VEVENT\n'
         u'SUMMARY:Eine Kurzinfo\n'
         u'DESCRIPTION:Beschreibung des Termines\n'
         u'END:VEVENT'),
        (u'BEGIN:VEVENT\n'
         u'SUMMARY:Eine zweite Küèrzinfo\n'
         u'DESCRIPTION:Beschreibung des anderen Termines\n'
         u'BEGIN:VALARM\n'
         u'ACTION:AUDIO\n'
         u'TRIGGER:19980403T120000\n'
         u'ATTACH;FMTTYPE=audio/basic:http://host.com/pub/ssbanner.aud\n'
         u'REPEAT:4\n'
         u'DURATION:PT1H\n'
         u'END:VALARM\n'
         u'END:VEVENT')
    ]

    responses = [
        u'\n'.join([u'BEGIN:VCALENDAR'] + items + [u'END:VCALENDAR'])
    ] * 2

    def get(method, url, *a, **kw):
        assert method == 'GET'
        assert url == collection_url
        r = Response()
        r.status_code = 200
        assert responses
        r._content = responses.pop().encode('utf-8')
        r.headers['Content-Type'] = 'text/icalendar'
        r.encoding = 'ISO-8859-1'
        return r

    monkeypatch.setattr('requests.request', get)

    s = HttpStorage(url=collection_url)

    found_items = {}

    for href, etag in s.list():
        item, etag2 = s.get(href)
        assert item.uid is None
        assert etag2 == etag
        found_items[normalize_item(item)] = href

    expected = set(normalize_item(u'BEGIN:VCALENDAR\n' + x + '\nEND:VCALENDAR')
                   for x in items)

    assert set(found_items) == expected

    for href, etag in s.list():
        item, etag2 = s.get(href)
        assert item.uid is None
        assert etag2 == etag
        assert found_items[normalize_item(item)] == href
