
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.test_carddav
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

from vdirsyncer.storage.dav.carddav import CarddavStorage
from . import DavStorageTests


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
UID:{uid}
X-SOMETHING:{r}
END:VCARD'''


class TestCarddavStorage(DavStorageTests):
    storage_class = CarddavStorage
    item_template = VCARD_TEMPLATE
