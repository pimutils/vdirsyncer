import os

from vdirsyncer.cli.config import _resolve_conflict_via_command
from vdirsyncer.vobject import Item


def test_conflict_resolution_command():
    def check_call(command):
        command, a_tmp, b_tmp = command
        assert command == os.path.expanduser("~/command")
        with open(a_tmp) as f:
            assert f.read() == a.raw
        with open(b_tmp) as f:
            assert f.read() == b.raw

        with open(b_tmp, "w") as f:
            f.write(a.raw)

    a = Item("UID:AAAAAAA")
    b = Item("UID:BBBBBBB")
    assert (
        _resolve_conflict_via_command(
            a, b, ["~/command"], "a", "b", _check_call=check_call
        ).raw
        == a.raw
    )
