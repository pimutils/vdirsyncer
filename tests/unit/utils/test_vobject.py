# -*- coding: utf-8 -*-

from textwrap import dedent

import hypothesis.strategies as st
from hypothesis import assume, given
from hypothesis.stateful import Bundle, RuleBasedStateMachine, rule

import pytest

from tests import BARE_EVENT_TEMPLATE, EVENT_TEMPLATE, \
    EVENT_WITH_TIMEZONE_TEMPLATE, VCARD_TEMPLATE, normalize_item, \
    uid_strategy

import vdirsyncer.vobject as vobject


_simple_split = [
    VCARD_TEMPLATE.format(r=123, uid=123),
    VCARD_TEMPLATE.format(r=345, uid=345),
    VCARD_TEMPLATE.format(r=678, uid=678)
]

_simple_joined = u'\r\n'.join(
    [u'BEGIN:VADDRESSBOOK'] +
    _simple_split +
    [u'END:VADDRESSBOOK\r\n']
)


def test_split_collection_simple(benchmark):
    given = benchmark(lambda: list(vobject.split_collection(_simple_joined)))

    assert [normalize_item(item) for item in given] == \
        [normalize_item(item) for item in _simple_split]

    assert [x.splitlines() for x in given] == \
        [x.splitlines() for x in _simple_split]


def test_split_collection_multiple_wrappers(benchmark):
    joined = u'\r\n'.join(
        u'BEGIN:VADDRESSBOOK\r\n' +
        x +
        u'\r\nEND:VADDRESSBOOK\r\n'
        for x in _simple_split
    )
    given = benchmark(lambda: list(vobject.split_collection(joined)))

    assert [normalize_item(item) for item in given] == \
        [normalize_item(item) for item in _simple_split]

    assert [x.splitlines() for x in given] == \
        [x.splitlines() for x in _simple_split]


def test_join_collection_simple(benchmark):
    given = benchmark(lambda: vobject.join_collection(_simple_split))
    assert normalize_item(given) == normalize_item(_simple_joined)
    assert given.splitlines() == _simple_joined.splitlines()


def test_join_collection_vevents(benchmark):
    actual = benchmark(lambda: vobject.join_collection([
        dedent("""
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:HUEHUE
            BEGIN:VTIMEZONE
            VALUE:The Timezone
            END:VTIMEZONE
            BEGIN:VEVENT
            VALUE:Event {}
            END:VEVENT
            END:VCALENDAR
         """).format(i) for i in range(3)
    ]))

    expected = dedent("""
        BEGIN:VCALENDAR
        VERSION:2.0
        PRODID:HUEHUE
        BEGIN:VTIMEZONE
        VALUE:The Timezone
        END:VTIMEZONE
        BEGIN:VEVENT
        VALUE:Event 0
        END:VEVENT
        BEGIN:VEVENT
        VALUE:Event 1
        END:VEVENT
        BEGIN:VEVENT
        VALUE:Event 2
        END:VEVENT
        END:VCALENDAR
    """).lstrip()

    assert actual.splitlines() == expected.splitlines()


def test_split_collection_timezones():
    items = [
        BARE_EVENT_TEMPLATE.format(r=123, uid=123),
        BARE_EVENT_TEMPLATE.format(r=345, uid=345)
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


def test_split_contacts():
    bare = '\r\n'.join([VCARD_TEMPLATE.format(r=x, uid=x) for x in range(4)])
    with_wrapper = 'BEGIN:VADDRESSBOOK\r\n' + bare + '\nEND:VADDRESSBOOK\r\n'

    for _ in (bare, with_wrapper):
        split = list(vobject.split_collection(bare))
        assert len(split) == 4
        assert vobject.join_collection(split).splitlines() == \
            with_wrapper.splitlines()


def test_hash_item():
    a = EVENT_TEMPLATE.format(r=1, uid=1)
    b = u'\n'.join(line for line in a.splitlines()
                   if u'PRODID' not in line)
    assert vobject.hash_item(a) == vobject.hash_item(b)


def test_multiline_uid(benchmark):
    a = (u'BEGIN:FOO\r\n'
         u'UID:123456789abcd\r\n'
         u' efgh\r\n'
         u'END:FOO\r\n')
    assert benchmark(lambda: vobject.Item(a).uid) == u'123456789abcdefgh'


complex_uid_item = dedent(u'''
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
    UID:040000008200E00074C5B7101A82E0080000000050AAABEEF50DCF
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
    ''').strip()


def test_multiline_uid_complex(benchmark):
    assert benchmark(lambda: vobject.Item(complex_uid_item).uid) == (
        u'040000008200E00074C5B7101A82E008000000005'
        u'0AAABEEF50DCF001000000062548482FA830A46B9'
        u'EA62114AC9F0EF'
    )


def test_replace_multiline_uid(benchmark):
    def inner():
        return vobject.Item(complex_uid_item).with_uid('a').uid

    assert benchmark(inner) == 'a'


@pytest.mark.parametrize('template', [EVENT_TEMPLATE,
                                      EVENT_WITH_TIMEZONE_TEMPLATE,
                                      VCARD_TEMPLATE])
@given(uid=st.one_of(st.none(), uid_strategy))
def test_replace_uid(template, uid):
    item = vobject.Item(template.format(r=123, uid=123)).with_uid(uid)
    assert item.uid == uid
    if uid:
        assert item.raw.count('\nUID:{}'.format(uid)) == 1
    else:
        assert '\nUID:' not in item.raw


def test_broken_item():
    with pytest.raises(ValueError) as excinfo:
        vobject._Component.parse('END:FOO')

    assert 'Parsing error at line 1' in str(excinfo.value)

    item = vobject.Item('END:FOO')
    assert item.parsed is None


def test_multiple_items():
    with pytest.raises(ValueError) as excinfo:
        vobject._Component.parse([
            'BEGIN:FOO',
            'END:FOO',
            'BEGIN:FOO',
            'END:FOO',
        ])

    assert 'Found 2 components, expected one' in str(excinfo.value)

    c1, c2 = vobject._Component.parse([
        'BEGIN:FOO',
        'END:FOO',
        'BEGIN:FOO',
        'END:FOO',
    ], multiple=True)
    assert c1.name == c2.name == 'FOO'


def test_input_types():
    lines = ['BEGIN:FOO', 'FOO:BAR', 'END:FOO']

    for x in (lines, '\r\n'.join(lines), '\r\n'.join(lines).encode('ascii')):
        c = vobject._Component.parse(x)
        assert c.name == 'FOO'
        assert c.props == ['FOO:BAR']
        assert not c.subcomponents


value_strategy = st.text(
    st.characters(blacklist_categories=(
        'Zs', 'Zl', 'Zp',
        'Cc', 'Cs'
    ), blacklist_characters=':='),
    min_size=1
).filter(lambda x: x.strip() == x)


class VobjectMachine(RuleBasedStateMachine):
    Unparsed = Bundle('unparsed')
    Parsed = Bundle('parsed')

    @rule(target=Unparsed,
          joined=st.booleans(),
          encoded=st.booleans())
    def get_unparsed_lines(self, joined, encoded):
        rv = ['BEGIN:FOO', 'FOO:YES', 'END:FOO']
        if joined:
            rv = '\r\n'.join(rv)
            if encoded:
                rv = rv.encode('utf-8')
        elif encoded:
            assume(False)
        return rv

    @rule(unparsed=Unparsed, target=Parsed)
    def parse(self, unparsed):
        return vobject._Component.parse(unparsed)

    @rule(parsed=Parsed, target=Unparsed)
    def serialize(self, parsed):
        return list(parsed.dump_lines())

    @rule(c=Parsed,
          key=uid_strategy,
          value=uid_strategy)
    def add_prop(self, c, key, value):
        c[key] = value
        assert c[key] == value
        assert key in c
        assert c.get(key) == value
        dump = '\r\n'.join(c.dump_lines())
        assert key in dump and value in dump

    @rule(c=Parsed,
          key=uid_strategy,
          value=uid_strategy,
          params=st.lists(st.tuples(value_strategy, value_strategy)))
    def add_prop_raw(self, c, key, value, params):
        params_str = ','.join(k + '=' + v for k, v in params)
        c.props.insert(0, '{};{}:{}'.format(key, params_str, value))
        assert c[key] == value
        assert key in c
        assert c.get(key) == value

    @rule(c=Parsed, sub_c=Parsed)
    def add_component(self, c, sub_c):
        assume(sub_c is not c and sub_c not in c)
        c.subcomponents.append(sub_c)
        assert '\r\n'.join(sub_c.dump_lines()) in '\r\n'.join(c.dump_lines())

    @rule(c=Parsed)
    def sanity_check(self, c):
        c1 = vobject._Component.parse(c.dump_lines())
        assert c1 == c


TestVobjectMachine = VobjectMachine.TestCase


def test_component_contains():
    item = vobject._Component.parse([
        'BEGIN:FOO',
        'FOO:YES',
        'END:FOO'
    ])

    assert 'FOO' in item
    assert 'BAZ' not in item

    with pytest.raises(ValueError):
        42 in item
