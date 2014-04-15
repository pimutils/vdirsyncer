# -*- coding: utf-8 -*-
'''
    tests.storage.dav.test_main
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os
import pytest
import datetime
from textwrap import dedent

from .. import StorageTests
import vdirsyncer.exceptions as exceptions
from vdirsyncer.storage.base import Item
from vdirsyncer.storage.dav import CaldavStorage, CarddavStorage
import vdirsyncer.exceptions
import requests
import requests.exceptions


dav_server = os.environ.get('DAV_SERVER', '').strip() or 'radicale'


def _get_server_mixin(server_name):
    from . import __name__ as base
    x = __import__('{}.servers.{}'.format(base, server_name), fromlist=[''])
    return x.ServerMixin

ServerMixin = _get_server_mixin(dav_server)

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
    'VCARD': VCARD_TEMPLATE,
    'VEVENT': EVENT_TEMPLATE,
    'VTODO': TASK_TEMPLATE
}


class DavStorageTests(ServerMixin, StorageTests):
    def test_dav_broken_item(self):
        item = Item(u'UID:1')
        s = self._get_storage()
        try:
            s.upload(item)
        except (exceptions.Error, requests.exceptions.HTTPError):
            pass
        assert not list(s.list())

    @pytest.mark.xfail(dav_server == 'owncloud',
                       reason='See issue #16')
    def test_wrong_etag(self):
        super(DavStorageTests, self).test_wrong_etag()

    @pytest.mark.xfail(dav_server == 'owncloud',
                       reason='See issue #16')
    def test_update_nonexisting(self):
        super(DavStorageTests, self).test_update_nonexisting()


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
    def test_item_types_correctness(self, item_type):
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

    @pytest.mark.parametrize('item_types', [
        ('VTODO',),
        ('VEVENT',),
        ('VTODO', 'VEVENT'),
        ('VTODO', 'VEVENT', 'VJOURNAL')
    ])
    def test_item_types_performance(self, item_types, monkeypatch):
        kw = self.get_storage_args()
        s = self.storage_class(item_types=item_types, **kw)

        old_list = s._list
        calls = []

        def _list(*a, **kw):
            calls.append(None)
            return old_list(*a, **kw)

        monkeypatch.setattr(s, '_list', _list)

        list(s.list())
        assert len(calls) == len(item_types)

    @pytest.mark.xfail(dav_server == 'radicale',
                       reason='Radicale doesn\'t support timeranges.')
    def test_timerange_correctness(self):
        kw = self.get_storage_args()
        start_date = datetime.datetime(2013, 9, 10)
        end_date = datetime.datetime(2013, 9, 13)
        s = self.storage_class(start_date=start_date, end_date=end_date, **kw)

        too_old_item = self._create_bogus_item('1', item_template=dedent(u'''
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
            END:VCALENDAR
            ''').strip())

        too_new_item = self._create_bogus_item('2', item_template=dedent(u'''
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:-//hacksw/handcal//NONSGML v1.0//EN
            BEGIN:VEVENT
            DTSTART:20150714T170000Z
            DTEND:20150715T035959Z
            SUMMARY:Another Bastille Day Party
            X-SOMETHING:{r}
            UID:{uid}
            END:VEVENT
            END:VCALENDAR
            ''').strip())

        good_item = self._create_bogus_item('3', item_template=dedent(u'''
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:-//hacksw/handcal//NONSGML v1.0//EN
            BEGIN:VEVENT
            DTSTART:20130911T170000Z
            DTEND:20130912T035959Z
            SUMMARY:What's with all these Bastille Day Partys
            X-SOMETHING:{r}
            UID:{uid}
            END:VEVENT
            END:VCALENDAR
            ''').strip())

        s.upload(too_old_item)
        s.upload(too_new_item)
        href, etag = s.upload(good_item)

        assert list(s.list()) == [(href, etag)]

    def test_item_types_passed_as_string(self):
        kw = self.get_storage_args()
        a = self.storage_class(item_types='VTODO,VEVENT', **kw)
        b = self.storage_class(item_types=('VTODO', 'VEVENT'), **kw)
        assert a.item_types == b.item_types == ('VTODO', 'VEVENT')

    def test_invalid_resource(self, monkeypatch):
        calls = []
        args = self.get_storage_args(collection=None)

        def request(session, method, url, data=None, headers=None, auth=None,
                    verify=None):
            assert method == 'OPTIONS'
            assert url == args['url']
            calls.append(None)

            r = requests.Response()
            r.status_code = 200
            r._content = 'Hello World.'
            return r

        monkeypatch.setattr('requests.sessions.Session.request', request)

        with pytest.raises(vdirsyncer.exceptions.StorageError):
            self.storage_class(**args)
        assert len(calls) == 1

    def test_empty_get_multi_performance(self, monkeypatch):
        s = self._get_storage()

        def breakdown(*a, **kw):
            raise AssertionError('Expected not to be called.')

        monkeypatch.setattr('requests.sessions.Session.request', breakdown)

        assert list(s.get_multi([])) == []


class TestCarddavStorage(DavStorageTests):
    storage_class = CarddavStorage
    item_template = VCARD_TEMPLATE
