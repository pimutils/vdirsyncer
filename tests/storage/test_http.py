# -*- coding: utf-8 -*-
'''
    tests.storage.test_http
    ~~~~~~~~~~~~~~~~~~~~~~~

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

        items = [
            dedent(b'''
                    BEGIN:VEVENT
                    SUMMARY:Eine Kurzinfo
                    DESCRIPTION:Beschreibung des Termines
                    END:VEVENT
                   ''').strip(),
            dedent(b'''
                    BEGIN:VEVENT
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
                   ''').strip()
        ]

        responses = [
            '\n'.join([b'BEGIN:VCALENDAR'] + items + [b'END:VCALENDAR'])
        ] * 2

        def get(method, url, *a, **kw):
            assert method == 'GET'
            assert url == collection_url
            r = Response()
            r.status_code = 200
            assert responses
            r._content = responses.pop()
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
