# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                'etesync_server'))

from urllib.parse import quote as urlquote

import pytest

from etesync_server.wsgi import application
import wsgi_intercept
import wsgi_intercept.requests_intercept

from vdirsyncer.storage.etesync import EtesyncContacts, EtesyncCalendars

from .. import StorageTests


class EtesyncTests(StorageTests):
    @pytest.fixture
    def get_storage_args(self, request, get_item, tmpdir):
        if os.getenv('ETESYNC_TESTS', '') != 'true':
            pytest.skip('ETESYNC_TESTS != true')
        wsgi_intercept.requests_intercept.install()
        wsgi_intercept.add_wsgi_intercept('127.0.0.1', 8000,
                                          lambda: application)

        def teardown():
            wsgi_intercept.remove_wsgi_intercept('127.0.0.1', 8000)
            wsgi_intercept.requests_intercept.uninstall()

        request.addfinalizer(teardown)

        def inner(collection='test'):
            assert collection is not None

            rv = {
                'email': 'test@localhost',
                'db_path': str(tmpdir.join('etesync.db')),
                'secrets_dir': os.path.dirname(__file__),
                'server_url': 'http://127.0.0.1:8000/',
                'collection': collection
            }

            return self.storage_class.create_collection(**rv)
        return inner


class TestContacts(EtesyncTests):
    storage_class = EtesyncContacts

    @pytest.fixture(params=['VCARD'])
    def item_type(self, request):
        return request.param


class TestCalendars(EtesyncTests):
    storage_class = EtesyncCalendars

    @pytest.fixture(params=['VTODO', 'VEVENT'])
    def item_type(self, request):
        return request.param
