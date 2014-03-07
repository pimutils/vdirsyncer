# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.test_http
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from unittest import TestCase
from .. import assert_item_equals
from textwrap import dedent
from vdirsyncer.storage.http import HttpStorage, Item, split_collection


class HttpStorageTests(TestCase):

    def _get_storage(self, **kwargs):
        return HttpStorage(**kwargs)

    def test_split_collection(self):
        (item,) = list(split_collection(
            dedent(u'''
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:http://www.example.com/calendarapplication/
            METHOD:PUBLISH
            BEGIN:VEVENT
            UID:461092315540@example.com
            ORGANIZER;CN="Alice Balder, Example Inc.":MAILTO:alice@example.com
            LOCATION:Somewhere
            SUMMARY:Eine Kurzinfo
            DESCRIPTION:Beschreibung des Termines
            CLASS:PUBLIC
            DTSTART:20060910T220000Z
            DTEND:20060919T215900Z
            DTSTAMP:20060812T125900Z
            END:VEVENT
            END:VCALENDAR
            ''')
        ))
        assert_item_equals(item, Item(dedent(u'''
            BEGIN:VEVENT
            UID:461092315540@example.com
            ORGANIZER;CN="Alice Balder, Example Inc.":MAILTO:alice@example.com
            LOCATION:Somewhere
            SUMMARY:Eine Kurzinfo
            DESCRIPTION:Beschreibung des Termines
            CLASS:PUBLIC
            DTSTART:20060910T220000Z
            DTEND:20060919T215900Z
            DTSTAMP:20060812T125900Z
            END:VEVENT
            ''').strip()))
