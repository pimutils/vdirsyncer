import os

import pytest


class ServerMixin:

    @pytest.fixture
    def get_storage_args(self, slow_create_collection):
        def inner(collection='test'):
            args = {
                'username': os.environ['FASTMAIL_USERNAME'],
                'password': os.environ['FASTMAIL_PASSWORD']
            }

            if self.storage_class.fileext == '.ics':
                args['url'] = 'https://caldav.fastmail.com/'
            elif self.storage_class.fileext == '.vcf':
                args['url'] = 'https://carddav.fastmail.com/'
            else:
                raise RuntimeError()

            if collection is not None:
                args = slow_create_collection(self.storage_class, args,
                                              collection)
            return args
        return inner
