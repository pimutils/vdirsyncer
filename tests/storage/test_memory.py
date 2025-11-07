from __future__ import annotations

from typing import Any

import pytest

from vdirsyncer.storage.memory import MemoryStorage

from . import StorageTests


class TestMemoryStorage(StorageTests):
    storage_class = MemoryStorage
    supports_collections = False

    @pytest.fixture
    def get_storage_args(self) -> Any:
        async def inner(**args: Any) -> dict[str, Any]:
            return args

        return inner
