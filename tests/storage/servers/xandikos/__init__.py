from __future__ import annotations

from typing import Any
from typing import ClassVar

import pytest


class ServerMixin:
    storage_class: ClassVar[type[Any]]

    @pytest.fixture
    def get_storage_args(
        self,
        request: Any,
        tmpdir: Any,
        slow_create_collection: Any,
        xandikos_server: Any,
        aio_connector: Any,
    ) -> Any:
        async def inner(collection: str | None = "test") -> dict[str, Any]:
            url = "http://127.0.0.1:8000/"
            args = {"url": url, "connector": aio_connector}

            if collection is not None:
                args = await slow_create_collection(
                    self.storage_class,
                    args,
                    collection,
                )

            return args

        return inner
