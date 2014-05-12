# -*- coding: utf-8 -*-
'''
    tests.storage.test_http
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from requests import Response

from vdirsyncer.storage.http import HttpStorage, split_collection


def test_split_collection_timezones():
    items = [
        (
            u'BEGIN:VEVENT',
            u'SUMMARY:Eine Kurzinfo',
            u'DESCRIPTION:Beschreibung des Termines',
            u'END:VEVENT'
        ),
        (
            u'BEGIN:VEVENT',
            u'SUMMARY:Eine zweite Kurzinfo',
            u'DESCRIPTION:Beschreibung des anderen Termines',
            u' With an extra line for description',
            u'BEGIN:VALARM',
            u'ACTION:AUDIO',
            u'TRIGGER:19980403T120000',
            u'ATTACH;FMTTYPE=audio/basic:http://host.com/pub/ssbanner.aud',
            u'REPEAT:4',
            u'DURATION:PT1H',
            u'END:VALARM',
            u'END:VEVENT'
        )
    ]

    timezone = (
        u'BEGIN:VTIMEZONE',
        u'TZID:/mozilla.org/20070129_1/Asia/Tokyo',
        u'X-LIC-LOCATION:Asia/Tokyo',
        u'BEGIN:STANDARD',
        u'TZOFFSETFROM:+0900',
        u'TZOFFSETTO:+0900',
        u'TZNAME:JST',
        u'DTSTART:19700101T000000',
        u'END:STANDARD',
        u'END:VTIMEZONE'
    )

    full = list(
        (u'BEGIN:VCALENDAR',) +
        timezone + tuple(line for item in items for line in item) +
        (u'END:VCALENDAR',)
    )

    given = [tuple(x) for x in split_collection(full)]
    expected = [(u'BEGIN:VCALENDAR',) + timezone + item + (u'END:VCALENDAR',)
                for item in items]
    print(given)
    print(expected)
    assert given == expected


def test_list(monkeypatch):
    collection_url = 'http://127.0.0.1/calendar/collection.ics'

    items = [
        (u'BEGIN:VEVENT\n'
         u'SUMMARY:Eine Kurzinfo\n'
         u'DESCRIPTION:Beschreibung des Termines\n'
         u'END:VEVENT'),
        (u'BEGIN:VEVENT\n'
         u'SUMMARY:Eine zweite Kurzinfo\n'
         u'DESCRIPTION:Beschreibung des anderen Termines\n'
         u' With an extra line for description\n'
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
        r.encoding = 'utf-8'
        return r

    monkeypatch.setattr('requests.request', get)

    s = HttpStorage(url=collection_url)

    found_items = {}

    for href, etag in s.list():
        item, etag2 = s.get(href)
        assert item.uid is not None
        assert etag2 == etag
        found_items[item.raw.strip()] = href

    assert set(found_items) == set(u'BEGIN:VCALENDAR\n' + x + '\nEND:VCALENDAR'
                                   for x in items)

    for href, etag in s.list():
        item, etag2 = s.get(href)
        assert item.uid is not None
        assert etag2 == etag
        assert found_items[item.raw.strip()] == href
