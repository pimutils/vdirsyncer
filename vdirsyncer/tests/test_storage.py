# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.test_storage
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
__version__ = '0.1.0'

from unittest import TestCase
import os
import tempfile
import shutil
from vdirsyncer.storage.base import Item
from vdirsyncer.storage.filesystem import FilesystemStorage
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.storage.caldav import CaldavStorage
import vdirsyncer.exceptions as exceptions

class StorageTests(object):
    def _create_bogus_item(self, uid):
        return Item('''BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//dmfs.org//mimedir.icalendar//EN
BEGIN:VTODO
CREATED:20130721T142233Z
DTSTAMP:20130730T074543Z
LAST-MODIFIED;VALUE=DATE-TIME:20140122T151338Z
SEQUENCE:2
SUMMARY:Book: Kowlani - Tödlicher Staub
UID:{}
END:VTODO
END:VCALENDAR
'''.format(uid))
    def _get_storage(self, **kwargs):
        raise NotImplementedError()

    def test_generic(self):
        items = map(self._create_bogus_item, range(1, 10))
        s = self._get_storage()
        for item in items:
            s.upload(item)
        hrefs = (href for href, etag in s.list())
        for href in hrefs:
            assert s.has(href)
            obj, etag = s.get(href)
            assert 'UID:{}'.format(obj.uid) in obj.raw

    def test_upload_already_existing(self):
        s = self._get_storage()
        item = self._create_bogus_item(1)
        s.upload(item)
        self.assertRaises(exceptions.PreconditionFailed, s.upload, item)

    def test_update_nonexisting(self):
        s = self._get_storage()
        item = self._create_bogus_item(1)
        self.assertRaises(exceptions.PreconditionFailed, s.update, 'huehue', item, 123)

    def test_wrong_etag(self):
        s = self._get_storage()
        obj = self._create_bogus_item(1)
        href, etag = s.upload(obj)
        self.assertRaises(exceptions.PreconditionFailed, s.update, href, obj, 'lolnope')
        self.assertRaises(exceptions.PreconditionFailed, s.delete, href, 'lolnope')

    def test_delete_nonexisting(self):
        s = self._get_storage()
        self.assertRaises(exceptions.PreconditionFailed, s.delete, '1', 123)


class FilesystemStorageTests(TestCase, StorageTests):
    tmpdir = None
    def _get_storage(self, **kwargs):
        path = self.tmpdir = tempfile.mkdtemp()
        return FilesystemStorage(path=path, fileext='.txt', **kwargs)

    def tearDown(self):
        print("lol")
        if self.tmpdir is not None:
            shutil.rmtree(self.tmpdir)
            self.tmpdir = None

class MemoryStorageTests(TestCase, StorageTests):
    def _get_storage(self, **kwargs):
        return MemoryStorage(**kwargs)


class CaldavStorageTests(TestCase, StorageTests):
    tmpdir = None

    def _get_storage(self, **kwargs):
        self.tmpdir = tempfile.mkdtemp()
        os.environ['RADICALE_CONFIG'] = ''
        import radicale.config as radicale_config
        radicale_config.set('storage', 'type', 'filesystem')
        radicale_config.set('storage', 'filesystem_folder', self.tmpdir)
        radicale_config.set('rights', 'type', 'None')

        from radicale import Application
        app = Application()
        import radicale.log
        radicale.log.start()
        from werkzeug.test import Client
        from werkzeug.wrappers import BaseResponse as WerkzeugResponse
        class Response(object):
            '''Fake API of requests module'''
            def __init__(self, x):
                self.x = x
                self.status_code = x.status_code
                self.content = x.get_data(as_text=False)
                self.headers = x.headers

            def raise_for_status(self):
                '''copied from requests itself'''
                if 400 <= self.status_code < 600:
                    from requests.exceptions import HTTPError
                    raise HTTPError(str(self.status_code))

        c = Client(app, WerkzeugResponse)
        server = 'http://127.0.0.1'
        calendar_path = '/bob/test.ics/'
        full_url = server + calendar_path
        def x(method, item, data=None, headers=None):
            assert '/' not in item
            url = calendar_path + item
            r = c.open(path=url, method=method, data=data, headers=headers)
            r = Response(r)
            return r
        return CaldavStorage(full_url, _request_func=x)

    def tearDown(self):
        self.app = None
        if self.tmpdir is not None:
            shutil.rmtree(self.tmpdir)
            self.tmpdir = None
