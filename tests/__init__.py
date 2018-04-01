# -*- coding: utf-8 -*-
'''
Test suite for vdirsyncer.
'''

import random

import hypothesis.strategies as st

from vdirsyncer.vobject import Item

import urllib3
import urllib3.exceptions

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def blow_up(*a, **kw):
    raise AssertionError('Did not expect to be called.')


def assert_item_equals(a, b):
    assert a.hash == b.hash


VCARD_TEMPLATE = u'''BEGIN:VCARD
VERSION:3.0
FN:Cyrus Daboo
N:Daboo;Cyrus;;;
ADR;TYPE=POSTAL:;2822 Email HQ;Suite 2821;RFCVille;PA;15213;USA
EMAIL;TYPE=PREF:cyrus@example.com
NICKNAME:me
NOTE:Example VCard.
ORG:Self Employed
TEL;TYPE=VOICE:412 605 0499
TEL;TYPE=FAX:412 605 0705
URL;VALUE=URI:http://www.example.com
X-SOMETHING:{r}
UID:{uid}
END:VCARD'''

TASK_TEMPLATE = u'''BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//dmfs.org//mimedir.icalendar//EN
BEGIN:VTODO
CREATED:20130721T142233Z
DTSTAMP:20130730T074543Z
LAST-MODIFIED;VALUE=DATE-TIME:20140122T151338Z
SEQUENCE:2
SUMMARY:Book: Kowlani - Tödlicher Staub
X-SOMETHING:{r}
UID:{uid}
END:VTODO
END:VCALENDAR'''


BARE_EVENT_TEMPLATE = u'''BEGIN:VEVENT
DTSTART:19970714T170000Z
DTEND:19970715T035959Z
DTSTAMP:19970610T172345Z
SUMMARY:Bastille Day Party
X-SOMETHING:{r}
UID:{uid}
END:VEVENT'''


EVENT_TEMPLATE = u'''BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//hacksw/handcal//NONSGML v1.0//EN
''' + BARE_EVENT_TEMPLATE + u'''
END:VCALENDAR'''

EVENT_WITH_TIMEZONE_TEMPLATE = '''BEGIN:VCALENDAR
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
''' + BARE_EVENT_TEMPLATE + '''
END:VCALENDAR'''


SIMPLE_TEMPLATE = u'''BEGIN:FOO
UID:{uid}
X-SOMETHING:{r}
HAHA:YES
END:FOO'''

printable_characters_strategy = st.text(
    st.characters(blacklist_categories=(
        'Cc', 'Cs'
    ))
)

uid_strategy = st.text(
    st.characters(blacklist_categories=(
        'Zs', 'Zl', 'Zp',
        'Cc', 'Cs'
    )),
    min_size=1
).filter(lambda x: x.strip() == x)


def format_item(uid=None, item_template=VCARD_TEMPLATE):
    # assert that special chars are handled correctly.
    r = random.random()
    uid = uid or r
    return Item(item_template.format(r=r, uid=uid))
