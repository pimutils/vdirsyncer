# -*- coding: utf-8 -*-

import ldap3
import pytest

from vdirsyncer.storage.ldap import LDAPStorage

from . import StorageTests


class TestLDAPStorage(StorageTests):
    storage_class = LDAPStorage
    supports_collections = False

    @pytest.fixture
    def get_storage_args(self):
        uri = 'ldap://localhost'
        server = ldap3.Server('fake')
        conn = ldap3.Connection(server, client_strategy=ldap3.MOCK_SYNC)

        conn.strategy.add_entry('cn=user0,ou=test,o=lab', {'userPassword': 'test0000', 'sn': 'user0_sn', 'revision': 0})

        def inner(collection='test'):
            return {'uri': uri, 'conn': conn}
        return inner
