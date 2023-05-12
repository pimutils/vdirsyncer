"""
General-purpose fixtures for vdirsyncer's testsuite.
"""
import logging
import os

import aiohttp
import click_log
import pytest
import pytest_asyncio
from hypothesis import HealthCheck
from hypothesis import Verbosity
from hypothesis import settings


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
        suppress_health_check=HealthCheck.all(),
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
async def aio_session(event_loop):
    async with aiohttp.ClientSession() as session:
        yield session


@pytest_asyncio.fixture
async def aio_connector(event_loop):
    async with aiohttp.TCPConnector(limit_per_host=16) as conn:
        yield conn
