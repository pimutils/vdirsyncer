
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.test_caldav
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
__version__ = '0.1.0'

from unittest import TestCase
import os
import tempfile
import shutil
from vdirsyncer.storage.caldav import CaldavStorage
from . import StorageTests

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
