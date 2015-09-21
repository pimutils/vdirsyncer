# -*- coding: utf-8 -*-
'''
General-purpose fixtures for vdirsyncer's testsuite.
'''
import logging
import threading
import time

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


@pytest.fixture(autouse=True)
def no_thread_leak(request):
    before = threading.active_count()

    def check_after():
        for x in range(10):
            after = threading.active_count()
            if after == before:
                break
            time.sleep(0.001)

        assert after == before

    request.addfinalizer(check_after)
