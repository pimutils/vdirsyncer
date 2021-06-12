import pytest

from . import DAVStorageTests
from vdirsyncer.storage.dav import CardDAVStorage


class TestCardDAVStorage(DAVStorageTests):
    storage_class = CardDAVStorage

    @pytest.fixture(params=["VCARD"])
    def item_type(self, request):
        return request.param
