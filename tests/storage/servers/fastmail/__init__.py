import os

import pytest


username = os.environ.get('FASTMAIL_USERNAME', '').strip()
password = os.environ.get('FASTMAIL_PASSWORD', '').strip()


class ServerMixin(object):

    @pytest.fixture
    def get_storage_args(self, slow_create_collection):
        if not username:
            pytest.skip('Fastmail credentials not available')

        def inner(collection='test'):
            args = {'username': username, 'password': password}

            if self.storage_class.fileext == '.ics':
                args['url'] = 'https://caldav.messagingengine.com/'
            elif self.storage_class.fileext == '.vcf':
                args['url'] = 'https://carddav.messagingengine.com/'
            else:
                raise RuntimeError()

            if collection is not None:
                args = slow_create_collection(self.storage_class, args,
                                              collection)
            return args
        return inner
