from __future__ import annotations

from typing import Any
from typing import ClassVar

import pytest


class ServerMixin:
    storage_class: ClassVar[type[Any]]

    @pytest.fixture
    def get_storage_args(self) -> None:
        pytest.skip("DAV tests disabled.")
