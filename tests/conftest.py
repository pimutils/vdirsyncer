# -*- coding: utf-8 -*-
'''
    tests.conftest
    ~~~~~~~~~~~~~~

    General-purpose fixtures for vdirsyncer's testsuite.

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''
import pytest

import vdirsyncer.log


@pytest.fixture(autouse=True)
def setup_logging():
    vdirsyncer.log.set_level(vdirsyncer.log.logging.DEBUG)
    vdirsyncer.log.add_handler(vdirsyncer.log.stdout_handler)
