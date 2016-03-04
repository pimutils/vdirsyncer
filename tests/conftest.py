# -*- coding: utf-8 -*-
'''
General-purpose fixtures for vdirsyncer's testsuite.
'''
import logging
import os

import click_log
import pytest
from hypothesis import settings, Verbosity


@pytest.fixture(autouse=True)
def setup_logging():
    click_log.basic_config('vdirsyncer').setLevel(logging.DEBUG)


@pytest.fixture(autouse=True)
def suppress_py2_warning(monkeypatch):
    monkeypatch.setattr('vdirsyncer.cli._check_python2', lambda: None)


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
))
settings.register_profile("deterministic", settings(
    derandomize=True,
))

if os.getenv('DETERMINISTIC_TESTS').lower == 'true':
    settings.load_profile("deterministic")
elif os.getenv('CI').lower == 'true':
    settings.load_profile("ci")
