import os
import shutil
import sys

import pytest
import requests

from .. import StorageTests
from vdirsyncer.storage.etesync import EtesyncCalendars
from vdirsyncer.storage.etesync import EtesyncContacts


pytestmark = pytest.mark.skipif(
    os.getenv("ETESYNC_TESTS", "") != "true", reason="etesync tests disabled"
)


@pytest.fixture(scope="session")
def etesync_app(tmpdir_factory):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "etesync_server"))

    db = tmpdir_factory.mktemp("etesync").join("etesync.sqlite")
    shutil.copy(
        os.path.join(os.path.dirname(__file__), "etesync_server", "db.sqlite3"), str(db)
    )

    os.environ["ETESYNC_DB_PATH"] = str(db)
    from etesync_server.wsgi import application

    return application


class EtesyncTests(StorageTests):

    supports_metadata = False

    @pytest.fixture
    def get_storage_args(self, request, get_item, tmpdir, etesync_app):
        import wsgi_intercept
        import wsgi_intercept.requests_intercept

        wsgi_intercept.requests_intercept.install()
        wsgi_intercept.add_wsgi_intercept("127.0.0.1", 8000, lambda: etesync_app)

        def teardown():
            wsgi_intercept.remove_wsgi_intercept("127.0.0.1", 8000)
            wsgi_intercept.requests_intercept.uninstall()

        request.addfinalizer(teardown)

        with open(
            os.path.join(os.path.dirname(__file__), "test@localhost/auth_token")
        ) as f:
            token = f.read().strip()
        headers = {"Authorization": "Token " + token}
        r = requests.post(
            "http://127.0.0.1:8000/reset/", headers=headers, allow_redirects=False
        )
        assert r.status_code == 200

        def inner(collection="test"):
            rv = {
                "email": "test@localhost",
                "db_path": str(tmpdir.join("etesync.db")),
                "secrets_dir": os.path.dirname(__file__),
                "server_url": "http://127.0.0.1:8000/",
            }
            if collection is not None:
                rv = self.storage_class.create_collection(collection=collection, **rv)
            return rv

        return inner


class TestContacts(EtesyncTests):
    storage_class = EtesyncContacts

    @pytest.fixture(params=["VCARD"])
    def item_type(self, request):
        return request.param


class TestCalendars(EtesyncTests):
    storage_class = EtesyncCalendars

    @pytest.fixture(params=["VEVENT"])
    def item_type(self, request):
        return request.param
