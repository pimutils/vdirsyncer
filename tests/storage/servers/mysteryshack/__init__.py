# -*- coding: utf-8 -*-

import os
import subprocess
import time
import shutil

import pytest

import requests

testserver_repo = os.path.dirname(__file__)
make_sh = os.path.abspath(os.path.join(testserver_repo, 'make.sh'))


def wait():
    for i in range(100):
        try:
            requests.get('http://127.0.0.1:6767/', verify=False)
        except Exception as e:
            # Don't know exact exception class, don't care.
            # Also, https://github.com/kennethreitz/requests/issues/2192
            if 'connection refused' not in str(e).lower():
                raise
            time.sleep(2 ** i)
        else:
            return True
    return False


class ServerMixin(object):
    @pytest.fixture(scope='session')
    def setup_mysteryshack_server(self, xprocess):
        def preparefunc(cwd):
            return wait, ['sh', make_sh, 'testserver']

        subprocess.check_call(['sh', make_sh, 'testserver-config'])
        xprocess.ensure('mysteryshack_server', preparefunc)

        return subprocess.check_output([
            os.path.join(
                testserver_repo,
                'mysteryshack/target/debug/mysteryshack'
            ),
            '-c', '/tmp/mysteryshack/config',
            'user',
            'authorize',
            'testuser',
            'https://example.com',
            self.storage_class.scope + ':rw'
        ]).strip().decode()

    @pytest.fixture
    def get_storage_args(self, monkeypatch, setup_mysteryshack_server):
        from requests import Session

        monkeypatch.setitem(os.environ, 'OAUTHLIB_INSECURE_TRANSPORT', 'true')

        old_request = Session.request

        def request(self, method, url, **kw):
            url = url.replace('https://', 'http://')
            return old_request(self, method, url, **kw)

        monkeypatch.setattr(Session, 'request', request)
        shutil.rmtree('/tmp/mysteryshack/testuser/data', ignore_errors=True)
        shutil.rmtree('/tmp/mysteryshack/testuser/meta', ignore_errors=True)

        def inner(**kw):
            kw['account'] = 'testuser@127.0.0.1:6767'
            kw['access_token'] = setup_mysteryshack_server
            if self.storage_class.fileext == '.ics':
                kw.setdefault('collection', 'test')
            return kw
        return inner
