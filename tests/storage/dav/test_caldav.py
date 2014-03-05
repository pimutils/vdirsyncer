
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.test_caldav
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from unittest import TestCase

from vdirsyncer.storage.base import Item
from vdirsyncer.storage.dav.caldav import CaldavStorage
from . import DavStorageTests


TASK_TEMPLATE = u'''BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//dmfs.org//mimedir.icalendar//EN
BEGIN:VTODO
CREATED:20130721T142233Z
DTSTAMP:20130730T074543Z
LAST-MODIFIED;VALUE=DATE-TIME:20140122T151338Z
SEQUENCE:2
SUMMARY:Book: Kowlani - Tödlicher Staub
UID:{uid}
X-SOMETHING:{r}
END:VTODO
END:VCALENDAR'''


EVENT_TEMPLATE = u'''BEGIN:VCALENDAR
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//hacksw/handcal//NONSGML v1.0//EN
BEGIN:VEVENT
DTSTART:19970714T170000Z
DTEND:19970715T035959Z
SUMMARY:Bastille Day Party
X-SOMETHING:{r}
UID:{uid}
END:VEVENT
END:VCALENDAR'''


class CaldavStorageTests(TestCase, DavStorageTests):
    storage_class = CaldavStorage
    radicale_path = '/bob/test.ics/'

    item_template = TASK_TEMPLATE

    def test_both_vtodo_and_vevent(self):
        task = self._create_bogus_item(1, item_template=TASK_TEMPLATE)
        event = self._create_bogus_item(2, item_template=EVENT_TEMPLATE)
        s = self._get_storage()
        href_etag_task = s.upload(task)
        href_etag_event = s.upload(event)
        assert set(s.list()) == set([
            href_etag_task,
            href_etag_event
        ])
