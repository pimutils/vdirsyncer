# -*- coding: utf-8 -*-


import os

import pytest

from vdirsyncer.storage.remotestorage import \
    RemoteStorageCalendars, RemoteStorageContacts

from . import StorageTests, get_server_mixin

remotestorage_server = os.environ['REMOTESTORAGE_SERVER']
ServerMixin = get_server_mixin(remotestorage_server)


class RemoteStorageTests(ServerMixin, StorageTests):
    remotestorage_server = remotestorage_server


class TestCalendars(RemoteStorageTests):
    storage_class = RemoteStorageCalendars

    @pytest.fixture(params=['VTODO', 'VEVENT'])
    def item_type(self, request):
        return request.param


class TestContacts(RemoteStorageTests):
    storage_class = RemoteStorageContacts
    supports_collections = False

    @pytest.fixture(params=['VCARD'])
    def item_type(self, request):
        return request.param
