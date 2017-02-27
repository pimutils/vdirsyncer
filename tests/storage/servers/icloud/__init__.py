import os
import uuid

import pytest


def _clear_collection(s):
    for href, etag in s.list():
        s.delete(href, etag)


class ServerMixin(object):

    @pytest.fixture
    def get_storage_args(self):
        def inner(collection='test'):
            args = {
                'username': os.environ['ICLOUD_USERNAME'],
                'password': os.environ['ICLOUD_PASSWORD']
            }

            if self.storage_class.fileext == '.ics':
                args['url'] = 'https://caldav.icloud.com/'
            elif self.storage_class.fileext == '.vcf':
                args['url'] = 'https://contacts.icloud.com/'
            else:
                raise RuntimeError()

            assert collection.startswith('test')
            # iCloud requires a minimum length for collection names
            collection += str(uuid.uuid4())

            args = self.storage_class.create_collection(collection,
                                                           **args)
            s = self.storage_class(**args)
            _clear_collection(s)
            assert not list(s.list())

            return args
        return inner
