import os
import pytest
from io import StringIO
from textwrap import dedent

from vdirsyncer.cli.config import Config, _resolve_conflict_via_command
from vdirsyncer.vobject import Item


def test_conflict_resolution_command():
    def check_call(command):
        command, a_tmp, b_tmp = command
        assert command == os.path.expanduser('~/command')
        with open(a_tmp) as f:
            assert f.read() == a.raw
        with open(b_tmp) as f:
            assert f.read() == b.raw

        with open(b_tmp, 'w') as f:
            f.write(a.raw)

    a = Item('UID:AAAAAAA')
    b = Item('UID:BBBBBBB')
    assert _resolve_conflict_via_command(
        a, b, ['~/command'], 'a', 'b',
        _check_call=check_call
    ).raw == a.raw


def test_config_reader_invalid_collections():
    s = StringIO(dedent('''
    [general]
    status_path = "foo"

    [storage foo]
    type = "memory"

    [storage bar]
    type = "memory"

    [pair foobar]
    a = "foo"
    b = "bar"
    collections = [["a", "b", "c", "d"]]
    ''').strip())

    with pytest.raises(ValueError) as excinfo:
        Config.from_fileobject(s)

    assert 'Expected list of format' in str(excinfo.value)
