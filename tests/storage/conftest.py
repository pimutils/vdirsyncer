import contextlib
import subprocess
import time
import uuid

import aiostream
import pytest
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


@pytest.fixture
async def slow_create_collection(request, aio_connector):
    # We need to properly clean up because otherwise we might run into
    # storage limits.
    to_delete = []

    async def delete_collections():
        for s in to_delete:
            await s.session.request("DELETE", "")

    async def inner(cls, args, collection):
        assert collection.startswith("test")
        collection += "-vdirsyncer-ci-" + str(uuid.uuid4())

        args = await cls.create_collection(collection, **args)
        s = cls(**args)
        await _clear_collection(s)
        assert not await aiostream.stream.list(s.list())
        to_delete.append(s)
        return args

    yield inner

    await delete_collections()


async def _clear_collection(s):
    async for href, etag in s.list():
        s.delete(href, etag)
