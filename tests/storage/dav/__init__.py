
# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.dav
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os
import pytest

from .. import StorageTests
import vdirsyncer.exceptions as exceptions
from vdirsyncer.storage.base import Item
import requests.exceptions


dav_server = os.environ.get('DAV_SERVER', '').strip() or 'radicale_filesystem'
if dav_server.startswith('radicale_'):
    from ._radicale import ServerMixin
elif dav_server == 'owncloud':
    from ._owncloud import ServerMixin
else:
    raise RuntimeError('{} is not a known DAV server.'.format(dav_server))

try:
    import radicale
    radicale_version = radicale.VERSION
    del radicale
except ImportError:
    radicale_version = None


pytestmark = pytest.mark.xfail(
    dav_server == 'radicale_database' and radicale_version == '0.8',
    reason='Database storage of Radicale 0.8 is broken.')


class DavStorageTests(ServerMixin, StorageTests):
    def test_dav_broken_item(self):
        item = Item(u'UID:1')
        s = self._get_storage()
        try:
            s.upload(item)
        except (exceptions.Error, requests.exceptions.HTTPError):
            pass
        assert not list(s.list())
