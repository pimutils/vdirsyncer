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
        baikal_server: Any,
        aio_connector: Any,
    ) -> Any:
        async def inner(collection: str | None = "test") -> dict[str, Any]:
            base_url = "http://127.0.0.1:8002/"
            args = {
                "url": base_url,
                "username": "baikal",
                "password": "baikal",
                "connector": aio_connector,
            }

            if self.storage_class.fileext == ".vcf":
                args["url"] = base_url + "card.php/"
            else:
                args["url"] = base_url + "cal.php/"

            if collection is not None:
                args = await slow_create_collection(
                    self.storage_class,
                    args,
                    collection,
                )
            return args

        return inner
