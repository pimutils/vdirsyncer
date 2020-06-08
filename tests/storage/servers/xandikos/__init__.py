import pytest


class ServerMixin:
    @pytest.fixture
    def get_storage_args(self, request, tmpdir, slow_create_collection):
        def inner(collection="test"):
            url = "http://127.0.0.1:8000/"
            args = {"url": url}

            if collection is not None:
                args = slow_create_collection(self.storage_class, args, collection)
            return args

        return inner
