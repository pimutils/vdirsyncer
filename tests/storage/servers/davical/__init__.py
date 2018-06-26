import os
import pytest
import uuid

try:
    caldav_args = {
        # Those credentials are configured through the Travis UI
        'username': os.environ['DAVICAL_USERNAME'].strip(),
        'password': os.environ['DAVICAL_PASSWORD'].strip(),
        'url': 'https://caesar.lostpackets.de/davical-test/caldav.php/travis/',
    }
except KeyError as e:
    caldav_args = None


@pytest.mark.flaky(reruns=5)
class ServerMixin(object):
    @pytest.fixture
    def davical_args(self):
        if caldav_args is None:
            pytest.skip('Missing envkeys for davical')
        if self.storage_class.fileext == '.ics':
            return dict(caldav_args)
        elif self.storage_class.fileext == '.vcf':
            pytest.skip('No carddav')
        else:
            raise RuntimeError()

    @pytest.fixture
    def get_storage_args(self, davical_args, request):
        def inner(collection='test'):
            if collection is None:
                return davical_args

            assert collection.startswith('test')

            for _ in range(4):
                args = dict(davical_args)
                args['collection'] = collection + str(uuid.uuid4())
                args = self.storage_class.create_collection(**args)

                s = self.storage_class(**args)
                if not list(s.list()):
                    request.addfinalizer(s.delete_collection)
                    return args

            raise RuntimeError('Failed to find free collection.')
        return inner
