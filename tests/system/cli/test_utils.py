from __future__ import annotations

import sqlite3

import pytest

from vdirsyncer import exceptions
from vdirsyncer.cli.utils import handle_cli_error
from vdirsyncer.cli.utils import storage_instance_from_config
from vdirsyncer.cli.utils import storage_names


def test_handle_cli_error(capsys):
    try:
        raise exceptions.InvalidResponse("ayy lmao")
    except exceptions.InvalidResponse:
        handle_cli_error()

    _out, err = capsys.readouterr()
    assert "returned something vdirsyncer doesn't understand" in err
    assert "ayy lmao" in err


def test_handle_cli_error_database_locked(capsys):
    try:
        raise sqlite3.OperationalError("database is locked")
    except BaseException:
        handle_cli_error("my_pair/my_collection")

    _out, err = capsys.readouterr()
    assert "status database is locked" in err
    assert "my_pair/my_collection" in err
    assert "Traceback" not in err


def test_handle_cli_error_other_operational_error(capsys):
    with pytest.raises(sqlite3.OperationalError):
        try:
            raise sqlite3.OperationalError("no such table: status")
        except BaseException:
            handle_cli_error("my_pair/my_collection")


@pytest.mark.asyncio
async def test_storage_instance_from_config(monkeypatch, aio_connector):
    class Dummy:
        def __init__(self, **kw):
            assert kw == {"foo": "bar", "baz": 1}

    monkeypatch.setitem(storage_names._storages, "lol", Dummy)
    config = {"type": "lol", "foo": "bar", "baz": 1}
    storage = await storage_instance_from_config(config, connector=aio_connector)
    assert isinstance(storage, Dummy)
