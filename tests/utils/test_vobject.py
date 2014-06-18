# -*- coding: utf-8 -*-
'''
    tests.utils.vobject
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import vdirsyncer.utils.vobject as vobject

from .. import BARE_EVENT_TEMPLATE, EVENT_TEMPLATE, VCARD_TEMPLATE, \
    normalize_item

_simple_split = [
    VCARD_TEMPLATE.format(r=123),
    VCARD_TEMPLATE.format(r=345),
    VCARD_TEMPLATE.format(r=678)
]

_simple_joined = u'\r\n'.join(
    [u'BEGIN:VADDRESSBOOK'] +
    _simple_split +
    [u'END:VADDRESSBOOK\r\n']
)


def test_split_collection_simple():
    given = list(vobject.split_collection(_simple_joined))

    assert [normalize_item(item) for item in given] == \
        [normalize_item(item) for item in _simple_split]

    if vobject.ICALENDAR_ORIGINAL_ORDER_SUPPORT:
        assert [x.splitlines() for x in given] == \
            [x.splitlines() for x in _simple_split]


def test_split_collection_multiple_wrappers():
    joined = u'\r\n'.join(
        u'BEGIN:VADDRESSBOOK\r\n' +
        x +
        u'\r\nEND:VADDRESSBOOK\r\n'
        for x in _simple_split
    )
    given = list(vobject.split_collection(joined))

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


def test_multiline_uid():
    a = (u'BEGIN:FOO\r\n'
         u'UID:123456789abcd\r\n'
         u' efgh\r\n'
         u'END:FOO\r\n')
    assert vobject.Item(a).uid == u'123456789abcdefgh'


def test_multiline_uid_complex():
    a = u'''
BEGIN:VCALENDAR
BEGIN:VTIMEZONE
TZID:Europe/Rome
X-LIC-LOCATION:Europe/Rome
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=3
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
DTSTART:20140124T133000Z
DTEND:20140124T143000Z
DTSTAMP:20140612T090652Z
UID:040000008200E00074C5B7101A82E0080000000050AAABEEF50DCF0100000000000000
 001000000062548482FA830A46B9EA62114AC9F0EF
CREATED:20140110T102231Z
DESCRIPTION:Test.
LAST-MODIFIED:20140123T095221Z
LOCATION:25.12.01.51
SEQUENCE:0
STATUS:CONFIRMED
SUMMARY:Präsentation
TRANSP:OPAQUE
END:VEVENT
END:VCALENDAR
    '''.strip()
    assert vobject.Item(a).uid == (u'040000008200E00074C5B7101A82E008000000005'
                                   u'0AAABEEF50DCF0100000000000000001000000062'
                                   u'548482FA830A46B9EA62114AC9F0EF')
