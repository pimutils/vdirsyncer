# -*- coding: utf-8 -*-
'''
    tests.utils.vobject
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import vdirsyncer.utils.vobject as vobject

from .. import normalize_item, VCARD_TEMPLATE, BARE_EVENT_TEMPLATE, \
    EVENT_TEMPLATE

_simple_joined = u'\r\n'.join((
    u'BEGIN:VADDRESSBOOK',
    VCARD_TEMPLATE.format(r=123),
    VCARD_TEMPLATE.format(r=345),
    VCARD_TEMPLATE.format(r=678),
    u'END:VADDRESSBOOK\r\n'
))

_simple_split = [
    VCARD_TEMPLATE.format(r=123),
    VCARD_TEMPLATE.format(r=345),
    VCARD_TEMPLATE.format(r=678)
]


def test_split_collection_simple():
    given = list(vobject.split_collection(_simple_joined))
    assert [normalize_item(item) for item in given] == \
        [normalize_item(item) for item in _simple_split]
    if vobject.ICALENDAR_ORIGINAL_ORDER_SUPPORT:
        assert [x.splitlines() for x in given] == \
            [x.splitlines() for x in _simple_split]


def test_join_collection_simple():
    given = vobject.join_collection(_simple_split)
    assert normalize_item(given) == normalize_item(_simple_joined)
    if vobject.ICALENDAR_ORIGINAL_ORDER_SUPPORT:
        assert given.splitlines() == _simple_joined.splitlines()


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

    given = set(normalize_item(item)
                for item in vobject.split_collection(full))
    expected = set(
        normalize_item(u'\r\n'.join((
            u'BEGIN:VCALENDAR', item, timezone, u'END:VCALENDAR'
        )))
        for item in items
    )

    assert given == expected


def test_hash_item():
    a = EVENT_TEMPLATE.format(r=1)
    b = u'\n'.join(line for line in a.splitlines()
                   if u'PRODID' not in line and u'VERSION' not in line)
    assert vobject.hash_item(a) == vobject.hash_item(b)
