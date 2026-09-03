"""
General-purpose fixtures for vdirsyncer's testsuite.
"""

from __future__ import annotations

import inspect
import logging
import os
from unittest.mock import Mock

import aiohttp
import aioresponses.core as _aioresponses_core
import click_log
import pytest
import pytest_asyncio
from hypothesis import HealthCheck
from hypothesis import Verbosity
from hypothesis import settings

# Workaround for https://github.com/pnuckowski/aioresponses/issues/289
# Can be dropped once https://github.com/pnuckowski/aioresponses/pull/288 is merged
if "stream_writer" in inspect.signature(aiohttp.ClientResponse.__init__).parameters:

    class _CompatClientResponse(aiohttp.ClientResponse):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("stream_writer", Mock(output_size=0))
            super().__init__(*args, **kwargs)

    _aioresponses_core.ClientResponse = _CompatClientResponse


@pytest.fixture(autouse=True)
def setup_logging():
    click_log.basic_config("vdirsyncer").setLevel(logging.DEBUG)


try:
    import pytest_benchmark
except ImportError:

    @pytest.fixture
    def benchmark():
        return lambda x: x()

else:
    del pytest_benchmark


settings.register_profile(
    "ci",
    settings(
        max_examples=1000,
        verbosity=Verbosity.verbose,
        suppress_health_check=[HealthCheck.too_slow],
    ),
)
settings.register_profile(
    "deterministic",
    settings(
        derandomize=True,
        suppress_health_check=list(HealthCheck),
    ),
)
settings.register_profile("dev", settings(suppress_health_check=[HealthCheck.too_slow]))

if os.environ.get("DETERMINISTIC_TESTS", "false").lower() == "true":
    settings.load_profile("deterministic")
elif os.environ.get("CI", "false").lower() == "true":
    settings.load_profile("ci")
else:
    settings.load_profile("dev")


@pytest_asyncio.fixture
async def aio_session():
    async with aiohttp.ClientSession() as session:
        yield session


@pytest_asyncio.fixture
async def aio_connector():
    async with aiohttp.TCPConnector(limit_per_host=16) as conn:
        yield conn
