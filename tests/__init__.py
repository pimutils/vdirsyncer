# -*- coding: utf-8 -*-
'''
    tests
    ~~~~~

    Test suite for vdirsyncer.

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import vdirsyncer.log
from vdirsyncer.utils import text_type
vdirsyncer.log.set_level(vdirsyncer.log.logging.DEBUG)


def normalize_item(item):
    # - X-RADICALE-NAME is used by radicale, because hrefs don't really exist
    #   in their filesystem backend
    # - PRODID is changed by radicale for some reason after upload, but nobody
    #   cares about that anyway
    rv = []
    if not isinstance(item, text_type):
        item = item.raw

    for line in item.splitlines():
        line = line.strip()
        line = line.strip().split(u':', 1)
        if line[0] in ('X-RADICALE-NAME', 'PRODID', 'REV'):
            continue
        rv.append(u':'.join(line))
    return tuple(sorted(rv))


def assert_item_equals(a, b):
    assert normalize_item(a) == normalize_item(b)


VCARD_TEMPLATE = u'''BEGIN:VCARD
VERSION:3.0
FN:Cyrus Daboo
N:Daboo;Cyrus
ADR;TYPE=POSTAL:;2822 Email HQ;Suite 2821;RFCVille;PA;15213;USA
EMAIL;TYPE=INTERNET;TYPE=PREF:cyrus@example.com
NICKNAME:me
NOTE:Example VCard.
ORG:Self Employed
TEL;TYPE=WORK;TYPE=VOICE:412 605 0499
TEL;TYPE=FAX:412 605 0705
URL:http://www.example.com
X-SOMETHING:{r}
UID:{r}
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
UID:{r}
END:VTODO
END:VCALENDAR'''


BARE_EVENT_TEMPLATE = u'''BEGIN:VEVENT
DTSTART:19970714T170000Z
DTEND:19970715T035959Z
SUMMARY:Bastille Day Party
X-SOMETHING:{r}
UID:{r}
END:VEVENT'''


EVENT_TEMPLATE = u'''BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//hacksw/handcal//NONSGML v1.0//EN
''' + BARE_EVENT_TEMPLATE + u'''
END:VCALENDAR'''


SIMPLE_TEMPLATE = u'''BEGIN:FOO
UID:{r}
X-SOMETHING:{r}
HAHA:YES
END:FOO'''
