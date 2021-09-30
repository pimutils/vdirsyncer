import pytest

from vdirsyncer import exceptions
from vdirsyncer.cli.utils import handle_cli_error
from vdirsyncer.cli.utils import storage_instance_from_config
from vdirsyncer.cli.utils import storage_names


def test_handle_cli_error(capsys):
    try:
        raise exceptions.InvalidResponse("ayy lmao")
    except BaseException:
        handle_cli_error()

    out, err = capsys.readouterr()
    assert "returned something vdirsyncer doesn't understand" in err
    assert "ayy lmao" in err


@pytest.mark.asyncio
async def test_storage_instance_from_config(monkeypatch, aio_connector):
    class Dummy:
        def __init__(self, **kw):
            assert kw == {"foo": "bar", "baz": 1}

    monkeypatch.setitem(storage_names._storages, "lol", Dummy)
    config = {"type": "lol", "foo": "bar", "baz": 1}
    storage = await storage_instance_from_config(config, connector=aio_connector)
    assert isinstance(storage, Dummy)
