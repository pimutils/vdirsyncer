# -*- coding: utf-8 -*-

from mockldap import MockLdap
import pytest

from vdirsyncer.storage.ldap import LDAPStorage

from . import StorageTests


class TestLDAPStorage(StorageTests):
    storage_class = LDAPStorage
    supports_collections = False

    @pytest.fixture
    def get_storage_args(self, request):
        uri = 'ldap://localhost'
        mockldap = MockLdap({})
        mockldap.start()
        ldapobj = mockldap[uri]
        request.addfinalizer(mockldap.stop)

        def inner(collection='test'):
            return {'uri': uri}
        return inner
