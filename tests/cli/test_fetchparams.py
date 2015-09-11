# -*- coding: utf-8 -*-

from textwrap import dedent

import pytest


class EmptyKeyring(object):
    def get_password(self, *a, **kw):
        return None


@pytest.fixture(autouse=True)
def empty_password_storages(monkeypatch):
    monkeypatch.setattr('vdirsyncer.cli.fetchparams.keyring', EmptyKeyring())


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
        fileext.fetch = ["command", "echo", ".asdf"]
    '''.format(base=str(tmpdir))))

    foo = tmpdir.ensure('foo', dir=True)
    foo.ensure('a', dir=True)
    foo.ensure('b', dir=True)
    foo.ensure('c', dir=True)
    bar = tmpdir.ensure('bar', dir=True)
    bar.ensure('a', dir=True)
    bar.ensure('b', dir=True)
    bar.ensure('c', dir=True)

    result = runner.invoke(['discover'])
    assert not result.exception
    status = tmpdir.join('status').join('foobar.collections').read()
    assert 'foo' in status
    assert 'bar' in status
    assert 'asdf' not in status
    assert 'txt' not in status

    result = runner.invoke(['sync'])
    assert not result.exception
