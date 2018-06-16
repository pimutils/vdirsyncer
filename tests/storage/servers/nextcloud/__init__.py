import os
import requests
import pytest


port = os.environ.get('NEXTCLOUD_HOST', None) or 'localhost:5000'
user = os.environ.get('NEXTCLOUD_USER', None) or 'asdf'
pwd = os.environ.get('NEXTCLOUD_PASS', None) or 'asdf'


class ServerMixin(object):
    storage_class = None
    wsgi_teardown = None

    @pytest.fixture
    def get_storage_args(self, item_type,
                         slow_create_collection):
        def inner(collection='test'):
            url = 'http://{}/remote.php/dav/{}/asdf/'.format(
                port,
                'calendars'
                if self.storage_class.fileext == '.ics'
                else 'addressbooks/users'
            )
            args = {
                'username': user,
                'password': pwd,
                'url': url
            }

            if collection is not None:
                args = slow_create_collection(self.storage_class, args,
                                              collection)
            return args
        return inner
