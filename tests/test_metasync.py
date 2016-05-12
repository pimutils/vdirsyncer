# -*- coding: utf-8 -*-

from hypothesis import example, given
import hypothesis.strategies as st

import pytest

from vdirsyncer.metasync import MetaSyncConflict, metasync
from vdirsyncer.storage.base import normalize_meta_value
from vdirsyncer.storage.memory import MemoryStorage

from . import blow_up


def test_irrelevant_status():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {'foo': 'bar'}

    metasync(a, b, status, keys=())
    assert not status


def test_basic(monkeypatch):
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}

    a.set_meta('foo', 'bar')
    metasync(a, b, status, keys=['foo'])
    assert a.get_meta('foo') == b.get_meta('foo') == 'bar'

    a.set_meta('foo', 'baz')
    metasync(a, b, status, keys=['foo'])
    assert a.get_meta('foo') == b.get_meta('foo') == 'baz'

    monkeypatch.setattr(a, 'set_meta', blow_up)
    monkeypatch.setattr(b, 'set_meta', blow_up)
    metasync(a, b, status, keys=['foo'])
    assert a.get_meta('foo') == b.get_meta('foo') == 'baz'
    monkeypatch.undo()
    monkeypatch.undo()

    b.set_meta('foo', None)
    metasync(a, b, status, keys=['foo'])
    assert not a.get_meta('foo') and not b.get_meta('foo')


def test_conflict():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    a.set_meta('foo', 'bar')
    b.set_meta('foo', 'baz')

    with pytest.raises(MetaSyncConflict):
        metasync(a, b, status, keys=['foo'])

    assert a.get_meta('foo') == 'bar'
    assert b.get_meta('foo') == 'baz'
    assert not status


def test_conflict_same_content():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    a.set_meta('foo', 'bar')
    b.set_meta('foo', 'bar')

    metasync(a, b, status, keys=['foo'])
    assert a.get_meta('foo') == b.get_meta('foo') == status['foo'] == 'bar'


@pytest.mark.parametrize('wins', 'ab')
def test_conflict_x_wins(wins):
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    a.set_meta('foo', 'bar')
    b.set_meta('foo', 'baz')

    metasync(a, b, status, keys=['foo'],
             conflict_resolution='a wins' if wins == 'a' else 'b wins')

    assert a.get_meta('foo') == b.get_meta('foo') == status['foo'] == (
        'bar' if wins == 'a' else 'baz'
    )


keys = st.text(min_size=1).filter(lambda x: x.strip() == x)
values = st.text().filter(lambda x: normalize_meta_value(x) == x)
metadata = st.dictionaries(keys, values)


@given(
    a=metadata, b=metadata,
    status=metadata, keys=st.sets(keys),
    conflict_resolution=st.just('a wins') | st.just('b wins')
)
@example(a={u'0': u'0'}, b={}, status={u'0': u'0'}, keys={u'0'},
         conflict_resolution='a wins')
def test_fuzzing(a, b, status, keys, conflict_resolution):
    def _get_storage(m, instance_name):
        s = MemoryStorage(instance_name=instance_name)
        s.metadata = m
        return s

    a = _get_storage(a, 'A')
    b = _get_storage(b, 'B')

    winning_storage = (a if conflict_resolution == 'a wins' else b)
    expected_values = dict((key, winning_storage.get_meta(key))
                           for key in keys)

    metasync(a, b, status,
             keys=keys, conflict_resolution=conflict_resolution)

    for key in keys:
        s = status.get(key, '')
        assert a.get_meta(key) == b.get_meta(key) == s
        assert s == expected_values[key] or not expected_values[key] or not s
