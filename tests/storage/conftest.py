import asyncio
import contextlib
import subprocess
import time
import uuid
from typing import Type

import aiostream
import pytest
import pytest_asyncio
import requests


def wait_for_container(url):
    """Wait for a container to initialise.

    Polls a URL every 100ms until the server responds.
    """
    # give the server 5 seconds to settle
    for _ in range(50):
        print(_)

        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.ConnectionError:
            pass
        else:
            return

        time.sleep(0.1)

    pytest.exit(
        "Server did not initialise in 5 seconds.\n"
        "WARNING: There may be a stale docker container still running."
    )


@contextlib.contextmanager
def dockerised_server(name, container_port, exposed_port):
    """Run a dockerised DAV server as a contenxt manager."""
    container_id = None
    url = f"http://127.0.0.1:{exposed_port}/"

    try:
        # Hint: This will block while the pull happends, and only return once
        # the container has actually started.
        output = subprocess.check_output(
            [
                "docker",
                "run",
                "--rm",
                "--detach",
                "--publish",
                f"{exposed_port}:{container_port}",
                f"whynothugo/vdirsyncer-devkit-{name}",
            ]
        )

        container_id = output.decode().strip()
        wait_for_container(url)

        yield url
    finally:
        if container_id:
            subprocess.check_output(["docker", "kill", container_id])


@pytest.fixture(scope="session")
def baikal_server():
    with dockerised_server("baikal", "80", "8002"):
        yield


@pytest.fixture(scope="session")
def radicale_server():
    with dockerised_server("radicale", "8001", "8001"):
        yield


@pytest.fixture(scope="session")
def xandikos_server():
    with dockerised_server("xandikos", "8000", "8000"):
        yield


@pytest_asyncio.fixture
async def slow_create_collection(request, aio_connector):
    # We need to properly clean up because otherwise we might run into
    # storage limits.
    to_delete = []

    async def inner(cls: Type, args: dict, collection_name: str) -> dict:
        """Create a collection

        Returns args necessary to create a Storage instance pointing to it.
        """
        assert collection_name.startswith("test")

        # Make each name unique
        collection_name = f"{collection_name}-vdirsyncer-ci-{uuid.uuid4()}"

        # Create the collection:
        args = await cls.create_collection(collection_name, **args)
        collection = cls(**args)

        # Keep collection in a list to be deleted once tests end:
        to_delete.append(collection)

        assert not await aiostream.stream.list(collection.list())
        return args

    yield inner

    await asyncio.gather(*(c.session.request("DELETE", "") for c in to_delete))
