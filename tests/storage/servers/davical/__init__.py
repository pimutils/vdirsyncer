from __future__ import annotations

import os
import uuid
from typing import Any
from typing import ClassVar

import pytest

try:
    caldav_args = {
        # Those credentials are configured through the Travis UI
        "username": os.environ["DAVICAL_USERNAME"].strip(),
        "password": os.environ["DAVICAL_PASSWORD"].strip(),
        "url": "https://brutus.lostpackets.de/davical-test/caldav.php/",
    }
except KeyError as e:
    pytestmark = pytest.mark.skip(f"Missing envkey: {e!s}")


@pytest.mark.flaky(reruns=5)
class ServerMixin:
    storage_class: ClassVar[type[Any]]

    @pytest.fixture
    def davical_args(self) -> dict[str, str]:
        if self.storage_class.fileext == ".ics":
            return dict(caldav_args)
        elif self.storage_class.fileext == ".vcf":
            pytest.skip("No carddav")
            return {}  # This line is never reached, but satisfies mypy
        else:
            raise RuntimeError

    @pytest.fixture
    def get_storage_args(self, davical_args: dict[str, str], request: Any) -> Any:
        async def inner(collection: str | None = "test") -> dict[str, Any]:
            if collection is None:
                return davical_args

            assert collection.startswith("test")

            for _ in range(4):
                args = self.storage_class.create_collection(
                    collection + str(uuid.uuid4()),
                    **davical_args,
                )
                s = self.storage_class(**args)
                if not list(s.list()):
                    # See: https://stackoverflow.com/a/33984811
                    request.addfinalizer(lambda x=s: x.session.request("DELETE", ""))
                    return args

            raise RuntimeError("Failed to find free collection.")

        return inner
