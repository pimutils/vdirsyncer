from contextlib import contextmanager
from unittest.mock import patch

import hypothesis.strategies as st
import pytest
from hypothesis import given

from vdirsyncer import exceptions
from vdirsyncer.cli.fetchparams import expand_fetch_params
from vdirsyncer.cli.fetchparams import STRATEGIES


@pytest.fixture
def mystrategy(monkeypatch):
    def strategy(x):
        calls.append(x)
        return x

    calls = []
    monkeypatch.setitem(STRATEGIES, "mystrategy", strategy)
    return calls


@contextmanager
def dummy_strategy():
    def strategy(x):
        calls.append(x)
        return x

    calls = []
    with patch.dict(STRATEGIES, {"mystrategy": strategy}):
        yield calls


@pytest.fixture
def value_cache(monkeypatch):
    _cache = {}

    class FakeContext:
        fetched_params = _cache

        def find_object(self, _):
            return self

    def get_context(*a, **kw):
        return FakeContext()

    monkeypatch.setattr("click.get_current_context", get_context)
    return _cache


def test_key_conflict(monkeypatch, mystrategy):
    with pytest.raises(ValueError) as excinfo:
        expand_fetch_params({"foo": "bar", "foo.fetch": ["mystrategy", "baz"]})

    assert "Can't set foo.fetch and foo." in str(excinfo.value)


@given(s=st.text(), t=st.text(min_size=1))
def test_fuzzing(s, t):
    with dummy_strategy():
        config = expand_fetch_params({f"{s}.fetch": ["mystrategy", t]})

    assert config[s] == t


@pytest.mark.parametrize("value", [[], "lol", 42])
def test_invalid_fetch_value(mystrategy, value):
    with pytest.raises(ValueError) as excinfo:
        expand_fetch_params({"foo.fetch": value})

    assert "Expected a list" in str(
        excinfo.value
    ) or "Expected list of length > 0" in str(excinfo.value)


def test_unknown_strategy():
    with pytest.raises(exceptions.UserError) as excinfo:
        expand_fetch_params({"foo.fetch": ["unreal", "asdf"]})

    assert "Unknown strategy" in str(excinfo.value)


def test_caching(monkeypatch, mystrategy, value_cache):
    orig_cfg = {"foo.fetch": ["mystrategy", "asdf"]}

    rv = expand_fetch_params(orig_cfg)
    assert rv["foo"] == "asdf"
    assert mystrategy == ["asdf"]
    assert len(value_cache) == 1

    rv = expand_fetch_params(orig_cfg)
    assert rv["foo"] == "asdf"
    assert mystrategy == ["asdf"]
    assert len(value_cache) == 1

    value_cache.clear()
    rv = expand_fetch_params(orig_cfg)
    assert rv["foo"] == "asdf"
    assert mystrategy == ["asdf"] * 2
    assert len(value_cache) == 1


def test_failed_strategy(monkeypatch, value_cache):
    calls = []

    def strategy(x):
        calls.append(x)
        raise KeyboardInterrupt()

    monkeypatch.setitem(STRATEGIES, "mystrategy", strategy)

    orig_cfg = {"foo.fetch": ["mystrategy", "asdf"]}

    for _ in range(2):
        with pytest.raises(KeyboardInterrupt):
            expand_fetch_params(orig_cfg)

    assert len(value_cache) == 1
    assert len(calls) == 1


def test_empty_value(monkeypatch, mystrategy):
    with pytest.raises(exceptions.UserError) as excinfo:
        expand_fetch_params({"foo.fetch": ["mystrategy", ""]})

    assert "Empty value for foo.fetch, this most likely indicates an error" in str(
        excinfo.value
    )
