from __future__ import annotations

import os

import pytest


class ServerMixin:
    @pytest.fixture
    def get_storage_args(self, item_type, slow_create_collection):
        if item_type != "VEVENT":
            # iCloud collections can either be calendars or task lists.
            # See https://github.com/pimutils/vdirsyncer/pull/593#issuecomment-285941615  # noqa
            pytest.skip("iCloud doesn't support anything else than VEVENT")

        async def inner(collection="test"):
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
