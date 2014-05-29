# -*- coding: utf-8 -*-
'''
    tests.utils.vobject
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

from vdirsyncer.utils.vobject import split_collection, join_collection, \
    hash_item

from .. import normalize_item, SIMPLE_TEMPLATE, BARE_EVENT_TEMPLATE, \
    EVENT_TEMPLATE


_simple_joined = u'\r\n'.join((
    u'BEGIN:VADDRESSBOOK',
    SIMPLE_TEMPLATE.format(r=123),
    SIMPLE_TEMPLATE.format(r=345),
    SIMPLE_TEMPLATE.format(r=678),
    u'END:VADDRESSBOOK'
))

_simple_split = [
    SIMPLE_TEMPLATE.format(r=123),
    SIMPLE_TEMPLATE.format(r=345),
    SIMPLE_TEMPLATE.format(r=678)
]


def test_split_collection_simple():
    given = split_collection(_simple_joined)
    assert [normalize_item(item) for item in given] == \
        [normalize_item(item) for item in _simple_split]


def test_join_collection_simple():
    item_type = _simple_split[0].splitlines()[0][len(u'BEGIN:'):]
    given = join_collection(_simple_split, wrappers={
        item_type: (u'VADDRESSBOOK', ())
    })
    print(given)
    print(_simple_joined)
    assert normalize_item(given) == normalize_item(_simple_joined)


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


def test_hash_item():
    a = EVENT_TEMPLATE.format(r=1)
    b = u'\n'.join(line for line in a.splitlines()
                   if u'PRODID' not in line and u'VERSION' not in line)
    assert hash_item(a) == hash_item(b)
