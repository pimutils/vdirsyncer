from __future__ import annotations

import pytest


class ServerMixin:
    @pytest.fixture
    def get_storage_args(
        self,
        request,
        tmpdir,
        slow_create_collection,
        baikal_server,
        aio_connector,
    ):
        async def inner(collection="test"):
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
