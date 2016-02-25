# -*- coding: utf-8 -*-

from textwrap import dedent

from hypothesis import given
import hypothesis.strategies as st

import pytest

from vdirsyncer import exceptions
from vdirsyncer.cli.fetchparams import STRATEGIES, expand_fetch_params
from vdirsyncer.utils.compat import PY2


@pytest.fixture
def mystrategy(monkeypatch):
    def strategy(x):
        calls.append(x)
        return x
    calls = []
    monkeypatch.setitem(STRATEGIES, 'mystrategy', strategy)
    return calls


@pytest.fixture
def value_cache(monkeypatch):
    _cache = {}

    class FakeContext(object):
        fetched_params = _cache

        def find_object(self, _):
            return self

    def get_context(*a, **kw):
        return FakeContext()

    monkeypatch.setattr('click.get_current_context', get_context)
    return _cache


def test_get_password_from_command(tmpdir, runner):
    runner.write_with_general(dedent('''
        [pair foobar]
        a = foo
        b = bar
        collections = ["a", "b", "c"]

        [storage foo]
        type = filesystem
        path = {base}/foo/
        fileext.fetch = ["command", "echo", ".txt"]

        [storage bar]
        type = filesystem
        path = {base}/bar/
        fileext.fetch = ["prompt", "Fileext for bar"]
    '''.format(base=str(tmpdir))))

    foo = tmpdir.ensure('foo', dir=True)
    foo.ensure('a', dir=True)
    foo.ensure('b', dir=True)
    foo.ensure('c', dir=True)
    bar = tmpdir.ensure('bar', dir=True)
    bar.ensure('a', dir=True)
    bar.ensure('b', dir=True)
    bar.ensure('c', dir=True)

    result = runner.invoke(['discover'], input='.asdf\n')
    assert not result.exception
    status = tmpdir.join('status').join('foobar.collections').read()
    assert 'foo' in status
    assert 'bar' in status
    assert 'asdf' not in status
    assert 'txt' not in status

    foo.join('a').join('foo.txt').write('BEGIN:VCARD\nUID:foo\nEND:VCARD')
    result = runner.invoke(['sync'], input='.asdf\n')
    assert not result.exception
    assert [x.basename for x in bar.join('a').listdir()] == ['foo.asdf']


def test_key_conflict(monkeypatch, mystrategy):
    with pytest.raises(ValueError) as excinfo:
        expand_fetch_params({
            'foo': 'bar',
            'foo.fetch': ['mystrategy', 'baz']
        })

    assert 'Can\'t set foo.fetch and foo.' in str(excinfo.value)


@pytest.mark.skipif(PY2, reason='Don\'t care about Python 2')
@given(s=st.text(), t=st.text(min_size=1))
def test_fuzzing(s, t, mystrategy):
    config = expand_fetch_params({
        '{}.fetch'.format(s): ['mystrategy', t]
    })

    assert config[s] == t


@pytest.mark.parametrize('value', [
    [],
    'lol',
    42
])
def test_invalid_fetch_value(mystrategy, value):
    with pytest.raises(ValueError) as excinfo:
        expand_fetch_params({
            'foo.fetch': value
        })

    assert 'Expected a list' in str(excinfo.value) or \
        'Expected list of length > 0' in str(excinfo.value)


def test_unknown_strategy():
    with pytest.raises(exceptions.UserError) as excinfo:
        expand_fetch_params({
            'foo.fetch': ['unreal', 'asdf']
        })

    assert 'Unknown strategy' in str(excinfo.value)


def test_caching(monkeypatch, mystrategy, value_cache):
    orig_cfg = {'foo.fetch': ['mystrategy', 'asdf']}

    rv = expand_fetch_params(orig_cfg)
    assert rv['foo'] == 'asdf'
    assert mystrategy == ['asdf']
    assert len(value_cache) == 1

    rv = expand_fetch_params(orig_cfg)
    assert rv['foo'] == 'asdf'
    assert mystrategy == ['asdf']
    assert len(value_cache) == 1

    value_cache.clear()
    rv = expand_fetch_params(orig_cfg)
    assert rv['foo'] == 'asdf'
    assert mystrategy == ['asdf'] * 2
    assert len(value_cache) == 1


def test_failed_strategy(monkeypatch, value_cache):
    calls = []

    def strategy(x):
        calls.append(x)
        raise KeyboardInterrupt()

    monkeypatch.setitem(STRATEGIES, 'mystrategy', strategy)

    orig_cfg = {'foo.fetch': ['mystrategy', 'asdf']}

    for _ in range(2):
        with pytest.raises(KeyboardInterrupt):
            expand_fetch_params(orig_cfg)

    assert len(value_cache) == 1
    assert len(calls) == 1


def test_empty_value(monkeypatch, mystrategy):
    with pytest.raises(exceptions.UserError) as excinfo:
        expand_fetch_params({
            'foo.fetch': ['mystrategy', '']
        })

    assert 'Empty value for foo.fetch, this most likely indicates an error' \
        in str(excinfo.value)
