# -*- coding: utf-8 -*-

import os
import sys

import logging
import pytest

import radicale
import radicale.config

from urllib.parse import quote as urlquote

import wsgi_intercept
import wsgi_intercept.requests_intercept

logger = logging.getLogger(__name__)


class ServerMixin(object):

    @pytest.fixture(autouse=True)
    def setup(self, request, tmpdir):
        tmpdir.mkdir('bob')

        def get_app():
            config = radicale.config.load(())
            config.set('storage', 'filesystem_folder', str(tmpdir))
            config.set('rights', 'type', 'owner_only')

            app = radicale.Application(config, logger)

            def is_authenticated(user, password):
                return user == 'bob' and password == 'bob'

            app.is_authenticated = is_authenticated
            return app

        wsgi_intercept.requests_intercept.install()
        wsgi_intercept.add_wsgi_intercept('127.0.0.1', 80, get_app)

        def teardown():
            wsgi_intercept.remove_wsgi_intercept('127.0.0.1', 80)
            wsgi_intercept.requests_intercept.uninstall()
        request.addfinalizer(teardown)

    @pytest.fixture
    def get_storage_args(self, get_item):
        def inner(collection='test'):
            url = 'http://127.0.0.1/bob/'
            if collection is not None:
                collection += self.storage_class.fileext
                url = url.rstrip('/') + '/' + urlquote(collection)

            rv = {'url': url, 'username': 'bob', 'password': 'bob'}

            if collection is not None:
                rv = self.storage_class.create_collection(collection, **rv)
                s = self.storage_class(**rv)
                assert not list(s.list())

            return rv
        return inner
