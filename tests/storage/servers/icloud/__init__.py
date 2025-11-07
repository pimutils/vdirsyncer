from __future__ import annotations

import os
from typing import Any
from typing import ClassVar

import pytest


class ServerMixin:
    storage_class: ClassVar[type[Any]]

    @pytest.fixture
    def get_storage_args(self, item_type: str, slow_create_collection: Any) -> Any:
        if item_type != "VEVENT":
            # iCloud collections can either be calendars or task lists.
            # See https://github.com/pimutils/vdirsyncer/pull/593#issuecomment-285941615
            pytest.skip("iCloud doesn't support anything else than VEVENT")

        async def inner(collection: str | None = "test") -> dict[str, Any]:
            args = {
                "username": os.environ["ICLOUD_USERNAME"],
                "password": os.environ["ICLOUD_PASSWORD"],
            }

            if self.storage_class.fileext == ".ics":
                args["url"] = "https://caldav.icloud.com/"
            elif self.storage_class.fileext == ".vcf":
                args["url"] = "https://contacts.icloud.com/"
            else:
                raise RuntimeError

            if collection is not None:
                args = slow_create_collection(self.storage_class, args, collection)
            return args

        return inner
