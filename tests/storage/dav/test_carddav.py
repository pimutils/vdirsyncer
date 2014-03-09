
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.test_carddav
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from unittest import TestCase

from vdirsyncer.storage.dav.carddav import CarddavStorage
from . import DavStorageTests


class CarddavStorageTests(TestCase, DavStorageTests):
    storage_class = CarddavStorage

    item_template = (u'BEGIN:VCARD\n'
                     u'VERSION:3.0\n'
                     u'FN:Cyrus Daboo\n'
                     u'N:Daboo;Cyrus\n'
                     u'ADR;TYPE=POSTAL:;2822 Email HQ;'  # address continuing
                     u'Suite 2821;RFCVille;PA;15213;USA\n'  # on next line
                     u'EMAIL;TYPE=INTERNET,PREF:cyrus@example.com\n'
                     u'NICKNAME:me\n'
                     u'NOTE:Example VCard.\n'
                     u'ORG:Self Employed\n'
                     u'TEL;TYPE=WORK,VOICE:412 605 0499\n'
                     u'TEL;TYPE=FAX:412 605 0705\n'
                     u'URL:http://www.example.com\n'
                     u'UID:{uid}\n'
                     u'X-SOMETHING:{r}\n'
                     u'END:VCARD')
