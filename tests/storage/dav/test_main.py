# -*- coding: utf-8 -*-
'''
    tests.storage.dav.test_main
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''

import datetime
import os
from textwrap import dedent

import pytest

import requests
import requests.exceptions

from tests import EVENT_TEMPLATE, TASK_TEMPLATE, VCARD_TEMPLATE

import vdirsyncer.exceptions as exceptions
from vdirsyncer.storage.base import Item
from vdirsyncer.storage.dav import CaldavStorage, CarddavStorage, \
    _normalize_href

from .. import StorageTests


dav_server = os.environ.get('DAV_SERVER', '').strip() or 'radicale'


def _get_server_mixin(server_name):
    from . import __name__ as base
    x = __import__('{}.servers.{}'.format(base, server_name), fromlist=[''])
    return x.ServerMixin

ServerMixin = _get_server_mixin(dav_server)


templates = {
    'VCARD': VCARD_TEMPLATE,
    'VEVENT': EVENT_TEMPLATE,
    'VTODO': TASK_TEMPLATE
}


class DavStorageTests(ServerMixin, StorageTests):
    def test_dav_broken_item(self, s):
        item = Item(u'HAHA:YES')
        try:
            s.upload(item)
        except (exceptions.Error, requests.exceptions.HTTPError):
            pass
        assert not list(s.list())

    def test_dav_empty_get_multi_performance(self, s, monkeypatch):
        def breakdown(*a, **kw):
            raise AssertionError('Expected not to be called.')

        monkeypatch.setattr('requests.sessions.Session.request', breakdown)

        assert list(s.get_multi([])) == []


class TestCaldavStorage(DavStorageTests):
    storage_class = CaldavStorage

    item_template = TASK_TEMPLATE

    def test_both_vtodo_and_vevent(self, s, get_item):
        task = get_item(item_template=TASK_TEMPLATE)
        event = get_item(item_template=EVENT_TEMPLATE)
        href_etag_task = s.upload(task)
        href_etag_event = s.upload(event)
        assert set(s.list()) == set([
            href_etag_task,
            href_etag_event
        ])

    @pytest.mark.parametrize('item_type', ['VTODO', 'VEVENT'])
    def test_item_types_correctness(self, item_type, storage_args, get_item):
        other_item_type = 'VTODO' if item_type == 'VEVENT' else 'VEVENT'
        s = self.storage_class(item_types=(item_type,), **storage_args())
        try:
            s.upload(get_item(item_template=templates[other_item_type]))
            s.upload(get_item(item_template=templates[other_item_type]))
        except (exceptions.Error, requests.exceptions.HTTPError):
            pass
        href, etag = \
            s.upload(get_item(
                item_template=templates[item_type]))
        ((href2, etag2),) = s.list()
        assert href2 == href
        assert etag2 == etag

    @pytest.mark.parametrize('item_types', [
        ('VTODO',),
        ('VEVENT',),
        ('VTODO', 'VEVENT'),
        ('VTODO', 'VEVENT', 'VJOURNAL'),
        ()
    ])
    def test_item_types_performance(self, storage_args, item_types,
                                    monkeypatch, get_item):
        s = self.storage_class(item_types=item_types, **storage_args())
        item = get_item()
        href, etag = s.upload(item)

        old_dav_query = s._dav_query
        calls = []

        def _dav_query(*a, **kw):
            calls.append(None)
            return old_dav_query(*a, **kw)

        monkeypatch.setattr(s, '_dav_query', _dav_query)

        rv = list(s.list())
        if (dav_server != 'radicale' and not s.item_types) \
           or item.parsed.name in s.item_types:
            assert rv == [(href, etag)]
        assert len(calls) == (len(item_types) or 1)

    @pytest.mark.xfail(dav_server == 'radicale',
                       reason='Radicale doesn\'t support timeranges.')
    def test_timerange_correctness(self, storage_args, get_item):
        start_date = datetime.datetime(2013, 9, 10)
        end_date = datetime.datetime(2013, 9, 13)
        s = self.storage_class(start_date=start_date, end_date=end_date,
                               **storage_args())

        too_old_item = get_item(item_template=dedent(u'''
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:-//hacksw/handcal//NONSGML v1.0//EN
            BEGIN:VEVENT
            DTSTART:19970714T170000Z
            DTEND:19970715T035959Z
            SUMMARY:Bastille Day Party
            X-SOMETHING:{r}
            UID:{r}
            END:VEVENT
            END:VCALENDAR
            ''').strip())

        too_new_item = get_item(item_template=dedent(u'''
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:-//hacksw/handcal//NONSGML v1.0//EN
            BEGIN:VEVENT
            DTSTART:20150714T170000Z
            DTEND:20150715T035959Z
            SUMMARY:Another Bastille Day Party
            X-SOMETHING:{r}
            UID:{r}
            END:VEVENT
            END:VCALENDAR
            ''').strip())

        good_item = get_item(item_template=dedent(u'''
            BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:-//hacksw/handcal//NONSGML v1.0//EN
            BEGIN:VEVENT
            DTSTART:20130911T170000Z
            DTEND:20130912T035959Z
            SUMMARY:What's with all these Bastille Day Partys
            X-SOMETHING:{r}
            UID:{r}
            END:VEVENT
            END:VCALENDAR
            ''').strip())

        s.upload(too_old_item)
        s.upload(too_new_item)
        href, etag = s.upload(good_item)

        assert list(s.list()) == [(href, etag)]

    def test_item_types_passed_as_string(self, storage_args):
        kw = storage_args()
        a = self.storage_class(item_types='VTODO,VEVENT', **kw)
        b = self.storage_class(item_types=('VTODO', 'VEVENT'), **kw)
        assert a.item_types == b.item_types == ('VTODO', 'VEVENT')

    def test_invalid_resource(self, monkeypatch, storage_args):
        calls = []
        args = storage_args(collection=None)

        def request(session, method, url, data=None, headers=None, auth=None,
                    verify=None):
            assert url == args['url']
            calls.append(None)

            r = requests.Response()
            r.status_code = 200
            r._content = 'Hello World.'
            return r

        monkeypatch.setattr('requests.sessions.Session.request', request)

        with pytest.raises(ValueError):
            s = self.storage_class(**args)
            list(s.list())
        assert len(calls) == 1


class TestCarddavStorage(DavStorageTests):
    storage_class = CarddavStorage
    item_template = VCARD_TEMPLATE


@pytest.mark.parametrize('base,path', [
    ('http://example.com/', ''),
    ('http://example.com/L%C3%98/', '/L%C3%98'),
    ('http://example.com/LØ/', '/L%C3%98'),
])
def test_normalize_href(base, path):
    assert _normalize_href(base, 'asdf') == path + '/asdf'

    assert _normalize_href(base, 'hahah') == path + '/hahah'

    assert _normalize_href(base, 'whoops@vdirsyncer.vcf') == \
        path + '/whoops@vdirsyncer.vcf'

    assert _normalize_href(base, 'whoops%40vdirsyncer.vcf') == \
        path + '/whoops@vdirsyncer.vcf'

    assert _normalize_href(base, 'wh%C3%98ops@vdirsyncer.vcf') == \
        path + '/wh%C3%98ops@vdirsyncer.vcf'

    assert _normalize_href(base, 'whØops@vdirsyncer.vcf') == \
        path + '/wh%C3%98ops@vdirsyncer.vcf'
