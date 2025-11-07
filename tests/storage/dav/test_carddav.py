from __future__ import annotations

from typing import Any

import pytest

from vdirsyncer.storage.dav import CardDAVStorage

from . import DAVStorageTests


class TestCardDAVStorage(DAVStorageTests):
    storage_class = CardDAVStorage

    @pytest.fixture(params=["VCARD"])
    def item_type(self, request: Any) -> Any:
        return request.param
