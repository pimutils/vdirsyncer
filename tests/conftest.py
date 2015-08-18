# -*- coding: utf-8 -*-
'''
General-purpose fixtures for vdirsyncer's testsuite.
'''
import logging

import click_log

import pytest


@pytest.fixture(autouse=True)
def setup_logging():
    click_log.basic_config('vdirsyncer').setLevel(logging.DEBUG)


try:
    import pytest_benchmark
except ImportError:
    @pytest.fixture
    def benchmark():
        return lambda x: x()
else:
    del pytest_benchmark
