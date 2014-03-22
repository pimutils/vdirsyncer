# -*- coding: utf-8 -*-
'''
    vdirsyncer.tests.storage.dav.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

import os
import pytest
import requests
import requests.exceptions
import time

dav_server = os.environ.get('DAV_SERVER', '').strip() or 'radicale_filesystem'
php_sh = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '../../../owncloud-testserver/php.sh'
))


def wait():
    for i in range(10):
        try:
            requests.get('http://127.0.0.1:8080/')
        except requests.exceptions.ConnectionError:
            time.sleep(1)
        else:
            return True
    return False


if dav_server == 'owncloud':
    @pytest.fixture(autouse=True)
    def start_owncloud_server(xprocess):
        def preparefunc(cwd):
            return wait, ['sh', php_sh]

        xprocess.ensure('owncloud_server', preparefunc)
