import os

import pytest


class ServerMixin:
    @pytest.fixture
    def get_storage_args(self, item_type, slow_create_collection, aio_connector):
        if item_type == "VTODO":
            # Fastmail has non-standard support for TODOs
            # See https://github.com/pimutils/vdirsyncer/issues/824
            pytest.skip("Fastmail has non-standard VTODO support.")

        async def inner(collection="test"):
            args = {
                "username": os.environ["FASTMAIL_USERNAME"],
                "password": os.environ["FASTMAIL_PASSWORD"],
                "connector": aio_connector,
            }

            if self.storage_class.fileext == ".ics":
                args["url"] = "https://caldav.fastmail.com/"
            elif self.storage_class.fileext == ".vcf":
                args["url"] = "https://carddav.fastmail.com/"
            else:
                raise RuntimeError()

            if collection is not None:
                args = await slow_create_collection(
                    self.storage_class,
                    args,
                    collection,
                )

            return args

        return inner
