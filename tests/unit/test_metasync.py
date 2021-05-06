import hypothesis.strategies as st
import pytest
from hypothesis import example
from hypothesis import given

from tests import blow_up
from vdirsyncer.exceptions import UserError
from vdirsyncer.metasync import logger
from vdirsyncer.metasync import metasync
from vdirsyncer.metasync import MetaSyncConflict
from vdirsyncer.storage.base import normalize_meta_value
from vdirsyncer.storage.memory import MemoryStorage


def test_irrelevant_status():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {"foo": "bar"}

    metasync(a, b, status, keys=())
    assert not status


def test_basic(monkeypatch):
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}

    a.set_meta("foo", "bar")
    metasync(a, b, status, keys=["foo"])
    assert a.get_meta("foo") == b.get_meta("foo") == "bar"

    a.set_meta("foo", "baz")
    metasync(a, b, status, keys=["foo"])
    assert a.get_meta("foo") == b.get_meta("foo") == "baz"

    monkeypatch.setattr(a, "set_meta", blow_up)
    monkeypatch.setattr(b, "set_meta", blow_up)
    metasync(a, b, status, keys=["foo"])
    assert a.get_meta("foo") == b.get_meta("foo") == "baz"
    monkeypatch.undo()
    monkeypatch.undo()

    b.set_meta("foo", None)
    metasync(a, b, status, keys=["foo"])
    assert not a.get_meta("foo") and not b.get_meta("foo")


@pytest.fixture
def conflict_state(request):
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    a.set_meta("foo", "bar")
    b.set_meta("foo", "baz")

    def cleanup():
        assert a.get_meta("foo") == "bar"
        assert b.get_meta("foo") == "baz"
        assert not status

    request.addfinalizer(cleanup)

    return a, b, status


def test_conflict(conflict_state):
    a, b, status = conflict_state

    with pytest.raises(MetaSyncConflict):
        metasync(a, b, status, keys=["foo"])


def test_invalid_conflict_resolution(conflict_state):
    a, b, status = conflict_state

    with pytest.raises(UserError) as excinfo:
        metasync(a, b, status, keys=["foo"], conflict_resolution="foo")

    assert "Invalid conflict resolution setting" in str(excinfo.value)


def test_warning_on_custom_conflict_commands(conflict_state, monkeypatch):
    a, b, status = conflict_state
    warnings = []
    monkeypatch.setattr(logger, "warning", warnings.append)

    with pytest.raises(MetaSyncConflict):
        metasync(a, b, status, keys=["foo"], conflict_resolution=lambda *a, **kw: None)

    assert warnings == ["Custom commands don't work on metasync."]


def test_conflict_same_content():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    a.set_meta("foo", "bar")
    b.set_meta("foo", "bar")

    metasync(a, b, status, keys=["foo"])
    assert a.get_meta("foo") == b.get_meta("foo") == status["foo"] == "bar"


@pytest.mark.parametrize("wins", "ab")
def test_conflict_x_wins(wins):
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    a.set_meta("foo", "bar")
    b.set_meta("foo", "baz")

    metasync(
        a,
        b,
        status,
        keys=["foo"],
        conflict_resolution="a wins" if wins == "a" else "b wins",
    )

    assert (
        a.get_meta("foo")
        == b.get_meta("foo")
        == status["foo"]
        == ("bar" if wins == "a" else "baz")
    )


keys = st.text(min_size=1).filter(lambda x: x.strip() == x)
values = st.text().filter(lambda x: normalize_meta_value(x) == x)
metadata = st.dictionaries(keys, values)


@given(
    a=metadata,
    b=metadata,
    status=metadata,
    keys=st.sets(keys),
    conflict_resolution=st.just("a wins") | st.just("b wins"),
)
@example(
    a={"0": "0"}, b={}, status={"0": "0"}, keys={"0"}, conflict_resolution="a wins"
)
@example(
    a={"0": "0"},
    b={"0": "1"},
    status={"0": "0"},
    keys={"0"},
    conflict_resolution="a wins",
)
def test_fuzzing(a, b, status, keys, conflict_resolution):
    def _get_storage(m, instance_name):
        s = MemoryStorage(instance_name=instance_name)
        s.metadata = m
        return s

    a = _get_storage(a, "A")
    b = _get_storage(b, "B")

    winning_storage = a if conflict_resolution == "a wins" else b
    expected_values = {
        key: winning_storage.get_meta(key) for key in keys if key not in status
    }

    metasync(a, b, status, keys=keys, conflict_resolution=conflict_resolution)

    for key in keys:
        s = status.get(key, "")
        assert a.get_meta(key) == b.get_meta(key) == s
        if expected_values.get(key, "") and s:
            assert s == expected_values[key]
