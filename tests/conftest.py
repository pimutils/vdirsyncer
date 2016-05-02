# -*- coding: utf-8 -*-
'''
General-purpose fixtures for vdirsyncer's testsuite.
'''
import logging
import os

import click_log

from hypothesis import HealthCheck, Verbosity, settings

import pytest


@pytest.fixture(autouse=True)
def setup_logging():
    click_log.basic_config('vdirsyncer').setLevel(logging.DEBUG)


# XXX: Py2
@pytest.fixture(autouse=True)
def suppress_py2_warning(monkeypatch):
    monkeypatch.setattr('vdirsyncer.cli._check_python2', lambda _: None)


try:
    import pytest_benchmark
except ImportError:
    @pytest.fixture
    def benchmark():
        return lambda x: x()
else:
    del pytest_benchmark

settings.register_profile("ci", settings(
    max_examples=1000,
    verbosity=Verbosity.verbose,
    suppress_health_check=[HealthCheck.too_slow]
))
settings.register_profile("deterministic", settings(
    derandomize=True,
))

if os.environ['DETERMINISTIC_TESTS'].lower() == 'true':
    settings.load_profile("deterministic")
elif os.environ['CI'].lower() == 'true':
    settings.load_profile("ci")
