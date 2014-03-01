
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

from vdirsyncer.storage.caldav import CaldavStorage
from . import DavStorageTests


class CaldavStorageTests(TestCase, DavStorageTests):
    storage_class = CaldavStorage
