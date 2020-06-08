import pytest

from xandikos.web import XandikosApp, XandikosBackend, WellknownRedirector

import wsgi_intercept
import wsgi_intercept.requests_intercept


class ServerMixin:
    @pytest.fixture
    def get_storage_args(self, request, tmpdir, slow_create_collection):
        tmpdir.mkdir('xandikos')
        backend = XandikosBackend(path=str(tmpdir))
        cup = '/user/'
        backend.create_principal(cup, create_defaults=True)
        app = XandikosApp(backend, cup)

        app = WellknownRedirector(app, '/')

        wsgi_intercept.requests_intercept.install()
        wsgi_intercept.add_wsgi_intercept('127.0.0.1', 8080, lambda: app)

        def teardown():
            wsgi_intercept.remove_wsgi_intercept('127.0.0.1', 8080)
            wsgi_intercept.requests_intercept.uninstall()
        request.addfinalizer(teardown)

        def inner(collection='test'):
            url = 'http://127.0.0.1:8080/'
            args = {'url': url, 'collection': collection}

            if collection is not None:
                args = self.storage_class.create_collection(**args)
            return args
        return inner
