# -*- coding: utf-8 -*-
'''
    tests.utils.vobject
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from vdirsyncer.utils.vobject import split_collection

from .. import normalize_item, SIMPLE_TEMPLATE, BARE_EVENT_TEMPLATE


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
