# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.dav.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os
import pytest

dav_server = os.environ.get('DAV_SERVER', '').strip() or 'radicale_filesystem'
php_sh = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '../../../owncloud-testserver/php.sh'
))

if dav_server == 'owncloud':
    @pytest.fixture(autouse=True)
    def start_owncloud_server(xprocess):
        def preparefunc(cwd):
            return 'Listening on', ['sh', php_sh]

        xprocess.ensure('owncloud_server', preparefunc)
