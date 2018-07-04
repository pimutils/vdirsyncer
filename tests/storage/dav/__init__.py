# -*- coding: utf-8 -*-

import os

from .. import StorageTests, get_server_mixin


dav_server = os.environ.get('DAV_SERVER', 'skip')
ServerMixin = get_server_mixin(dav_server)


class DAVStorageTests(ServerMixin, StorageTests):
    dav_server = dav_server
