# -*- coding: utf-8 -*-
'''
    tests.storage.test_http
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

from requests import Response

from tests import normalize_item
from vdirsyncer.storage.http import HttpStorage


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
