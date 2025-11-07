from __future__ import annotations

from typing import Any

import pytest

from vdirsyncer import exceptions
from vdirsyncer.cli.utils import handle_cli_error
from vdirsyncer.cli.utils import storage_instance_from_config
from vdirsyncer.cli.utils import storage_names


def test_handle_cli_error(capsys: Any) -> None:
    try:
        raise exceptions.InvalidResponse("ayy lmao")
    except BaseException:
        handle_cli_error()

    _out, err = capsys.readouterr()
    assert "returned something vdirsyncer doesn't understand" in err
    assert "ayy lmao" in err


@pytest.mark.asyncio
async def test_storage_instance_from_config(
    monkeypatch: Any,
    aio_connector: Any,
) -> None:
    class Dummy:
        def __init__(self, **kw: Any) -> None:
            assert kw == {"foo": "bar", "baz": 1}

    monkeypatch.setitem(storage_names._storages, "lol", Dummy)
    config = {"type": "lol", "foo": "bar", "baz": 1}
    storage = await storage_instance_from_config(config, connector=aio_connector)
    assert isinstance(storage, Dummy)
