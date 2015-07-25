# -*- coding: utf-8 -*-

import pytest

from vdirsyncer.storage.dav import CarddavStorage

from . import DavStorageTests


class TestCarddavStorage(DavStorageTests):
    storage_class = CarddavStorage

    @pytest.fixture(params=['VCARD'])
    def item_type(self, request):
        return request.param
