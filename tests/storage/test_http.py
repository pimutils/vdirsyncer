# -*- coding: utf-8 -*-
'''
    tests.storage.test_http
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from vdirsyncer.storage.http import HttpStorage
from requests import Response


class TestHttpStorage(object):

    def test_list(self, monkeypatch):
        collection_url = 'http://127.0.0.1/calendar/collection.ics'

        items = [
            (u'BEGIN:VEVENT\n'
             u'SUMMARY:Eine Kurzinfo\n'
             u'DESCRIPTION:Beschreibung des Termines\n'
             u'END:VEVENT'),
            (u'BEGIN:VEVENT\n'
             u'SUMMARY:Eine zweite Kurzinfo\n'
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
            r.encoding = 'utf-8'
            return r

        monkeypatch.setattr('requests.request', get)

        s = HttpStorage(url=collection_url)

        found_items = {}

        for href, etag in s.list():
            item, etag2 = s.get(href)
            assert item.uid is None
            assert etag2 == etag
            found_items[item.raw.strip()] = href

        assert set(found_items) == set(items)

        for href, etag in s.list():
            item, etag2 = s.get(href)
            assert item.uid is None
            assert etag2 == etag
            assert found_items[item.raw.strip()] == href
