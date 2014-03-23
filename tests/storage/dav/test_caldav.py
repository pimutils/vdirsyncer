
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.test_caldav
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''


import pytest
import requests.exceptions
from vdirsyncer.storage.dav.caldav import CaldavStorage
import vdirsyncer.exceptions as exceptions
from . import DavStorageTests, pytestmark


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


templates = {
    'VEVENT': EVENT_TEMPLATE,
    'VTODO': TASK_TEMPLATE
}


class TestCaldavStorage(DavStorageTests):
    storage_class = CaldavStorage

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

    @pytest.mark.parametrize('item_type', ['VTODO', 'VEVENT'])
    def test_item_types(self, item_type):
        other_item_type = 'VTODO' if item_type == 'VEVENT' else 'VEVENT'
        kw = self.get_storage_args()
        s = self.storage_class(item_types=(item_type,), **kw)
        try:
            s.upload(self._create_bogus_item(
                1, item_template=templates[other_item_type]))
            s.upload(self._create_bogus_item(
                5, item_template=templates[other_item_type]))
        except (exceptions.Error, requests.exceptions.HTTPError):
            pass
        href, etag = \
            s.upload(self._create_bogus_item(
                3, item_template=templates[item_type]))
        ((href2, etag2),) = s.list()
        assert href2 == href
        assert etag2 == etag

    def test_item_types_passed_as_string(self):
        kw = self.get_storage_args()
        a = self.storage_class(item_types='VTODO,VEVENT', **kw)
        b = self.storage_class(item_types=('VTODO', 'VEVENT'), **kw)
        assert a.item_types == b.item_types == ('VTODO', 'VEVENT')
