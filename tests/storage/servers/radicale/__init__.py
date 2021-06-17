import pytest


class ServerMixin:
    @pytest.fixture
    def get_storage_args(
        self,
        request,
        tmpdir,
        slow_create_collection,
        radicale_server,
        aio_connector,
    ):
        async def inner(collection="test"):
            url = "http://127.0.0.1:8001/"
            args = {
                "url": url,
                "username": "radicale",
                "password": "radicale",
                "connector": aio_connector,
            }

            if collection is not None:
                args = await slow_create_collection(
                    self.storage_class,
                    args,
                    collection,
                )
            return args

        return inner
