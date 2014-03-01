
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.test_caldav
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
__version__ = '0.1.0'

from unittest import TestCase

from vdirsyncer.storage.base import Item
from vdirsyncer.storage.dav.caldav import CaldavStorage
from . import DavStorageTests


class CaldavStorageTests(TestCase, DavStorageTests):
    storage_class = CaldavStorage
    radicale_path = '/bob/test.ics/'

    def _create_bogus_item(self, uid):
        return Item(u'BEGIN:VCALENDAR\n'
                    u'VERSION:2.0\n'
                    u'PRODID:-//dmfs.org//mimedir.icalendar//EN\n'
                    u'BEGIN:VTODO\n'
                    u'CREATED:20130721T142233Z\n'
                    u'DTSTAMP:20130730T074543Z\n'
                    u'LAST-MODIFIED;VALUE=DATE-TIME:20140122T151338Z\n'
                    u'SEQUENCE:2\n'
                    u'SUMMARY:Book: Kowlani - Tödlicher Staub\n'
                    u'UID:{}\n'
                    u'END:VTODO\n'
                    u'END:VCALENDAR'.format(uid))
