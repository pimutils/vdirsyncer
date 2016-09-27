# -*- coding: utf-8 -*-

import pytest

from vdirsyncer.storage.dav import CardDAVStorage

from . import DAVStorageTests


class TestCardDAVStorage(DAVStorageTests):
    storage_class = CardDAVStorage

    @pytest.fixture(params=['VCARD'])
    def item_type(self, request):
        return request.param
