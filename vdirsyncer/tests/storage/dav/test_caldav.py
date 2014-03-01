
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.test_caldav
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Using an actual CalDAV server to test the CalDAV storage. Done by using
    Werkzeug's test client for WSGI apps. While this is pretty fast, Radicale
    has so much global state such that a clean separation of the unit tests is
    not guaranteed.

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

    def _create_bogus_item(self, uid):
        return Item(u'BEGIN:VCALENDAR'
                    u'VERSION:2.0'
                    u'PRODID:-//dmfs.org//mimedir.icalendar//EN'
                    u'BEGIN:VTODO'
                    u'CREATED:20130721T142233Z'
                    u'DTSTAMP:20130730T074543Z'
                    u'LAST-MODIFIED;VALUE=DATE-TIME:20140122T151338Z'
                    u'SEQUENCE:2'
                    u'SUMMARY:Book: Kowlani - Tödlicher Staub'
                    u'UID:{}'
                    u'END:VTODO'
                    u'END:VCALENDAR'.format(uid))
