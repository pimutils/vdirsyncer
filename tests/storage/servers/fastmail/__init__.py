import os

import pytest

args = {
    'username': os.environ['FASTMAIL_USERNAME'],
    'password': os.environ['FASTMAIL_PASSWORD']
}

carddav_args = dict(args)
carddav_args['url'] = (
    'https://carddav.messagingengine.com/dav/addressbooks/user/{}/'
    .format(carddav_args['username'])
)
caldav_args = dict(args)
caldav_args['url'] = (
    'https://caldav.messagingengine.com/dav/calendars/user/{}/'
    .format(carddav_args['username'])
)


def _clear_collection(s):
    for href, etag in s.list():
        s.delete(href, etag)


class ServerMixin(object):
    @pytest.fixture
    def fastmail_args(self):
        if self.storage_class.fileext == '.ics':
            args = caldav_args
        elif self.storage_class.fileext == '.vcf':
            args = carddav_args
        else:
            raise RuntimeError()

        return args

    @pytest.fixture
    def get_storage_args(self, fastmail_args, request):
        def inner(collection='test'):
            args = fastmail_args
            if collection is not None:
                assert collection.startswith('test')
                args = self.storage_class.create_collection(
                    collection=collection, **args
                )
                s = self.storage_class(**args)
                _clear_collection(s)
                assert not list(s.list())
            return args
        return inner
