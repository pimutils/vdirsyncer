import pytest


class ServerMixin(object):

    @pytest.fixture
    def get_storage_args(self):
        pytest.skip('DAV tests disabled.')
