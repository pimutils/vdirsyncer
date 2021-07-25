import pytest

from vdirsyncer.storage.memory import MemoryStorage

from . import StorageTests


class TestMemoryStorage(StorageTests):

    storage_class = MemoryStorage
    supports_collections = False

    @pytest.fixture
    def get_storage_args(self):
        async def inner(**args):
            return args

        return inner
