import pytest

from xandikos.web import XandikosApp, XandikosBackend

import wsgi_intercept
import wsgi_intercept.requests_intercept


class ServerMixin(object):
    @pytest.fixture
    def get_storage_args(self, request, tmpdir, slow_create_collection):
        backend = XandikosBackend(path=str(tmpdir.mkdir('xandikos')))
        cup = '/user/'
        backend._mark_as_principal(cup)
        app = XandikosApp(backend, cup)

        wsgi_intercept.requests_intercept.install()
        wsgi_intercept.add_wsgi_intercept('127.0.0.1', 8080, lambda: app)

        def teardown():
            wsgi_intercept.remove_wsgi_intercept('127.0.0.1', 8080)
            wsgi_intercept.requests_intercept.uninstall()
        request.addfinalizer(teardown)

        def inner(collection='test'):
            url = 'http://127.0.0.1:8080/user/'
            args = {'url': url}

            if collection is not None:
                args = slow_create_collection(self.storage_class, args,
                                              collection)
            return args
        return inner
