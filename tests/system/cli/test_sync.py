# -*- coding: utf-8 -*-

import json
import sys
from textwrap import dedent

import pytest

from tests import format_item


def test_simple_run(tmpdir, runner):
    runner.write_with_general(dedent('''
    [pair my_pair]
    a = "my_a"
    b = "my_b"
    collections = null

    [storage my_a]
    type = "filesystem"
    path = "{0}/path_a/"
    fileext = ".txt"

    [storage my_b]
    type = "filesystem"
    path = "{0}/path_b/"
    fileext = ".txt"
    ''').format(str(tmpdir)))

    tmpdir.mkdir('path_a')
    tmpdir.mkdir('path_b')

    result = runner.invoke(['discover'])
    assert not result.exception

    result = runner.invoke(['sync'])
    assert not result.exception

    item = format_item('haha')
    tmpdir.join('path_a/haha.txt').write(item.raw)
    result = runner.invoke(['sync'])
    assert 'Copying (uploading) item haha to my_b' in result.output
    assert tmpdir.join('path_b/haha.txt').read().splitlines() == \
        item.raw.splitlines()


def test_sync_inexistant_pair(tmpdir, runner):
    runner.write_with_general("")

    result = runner.invoke(['sync', 'foo'])
    assert result.exception
    assert 'pair foo does not exist.' in result.output.lower()


def test_debug_connections(tmpdir, runner):
    runner.write_with_general(dedent('''
    [pair my_pair]
    a = "my_a"
    b = "my_b"
    collections = null

    [storage my_a]
    type = "filesystem"
    path = "{0}/path_a/"
    fileext = ".txt"

    [storage my_b]
    type = "filesystem"
    path = "{0}/path_b/"
    fileext = ".txt"
    ''').format(str(tmpdir)))

    tmpdir.mkdir('path_a')
    tmpdir.mkdir('path_b')

    result = runner.invoke(['discover'])
    assert not result.exception

    result = runner.invoke(['-vdebug', 'sync', '--max-workers=3'])
    assert 'using 3 maximal workers' in result.output.lower()

    result = runner.invoke(['-vdebug', 'sync'])
    assert 'using 1 maximal workers' in result.output.lower()


def test_empty_storage(tmpdir, runner):
    runner.write_with_general(dedent('''
    [pair my_pair]
    a = "my_a"
    b = "my_b"
    collections = null

    [storage my_a]
    type = "filesystem"
    path = "{0}/path_a/"
    fileext = ".txt"

    [storage my_b]
    type = "filesystem"
    path = "{0}/path_b/"
    fileext = ".txt"
    ''').format(str(tmpdir)))

    tmpdir.mkdir('path_a')
    tmpdir.mkdir('path_b')

    result = runner.invoke(['discover'])
    assert not result.exception

    result = runner.invoke(['sync'])
    assert not result.exception

    item = format_item('haha')
    tmpdir.join('path_a/haha.txt').write(item.raw)
    result = runner.invoke(['sync'])
    assert not result.exception
    tmpdir.join('path_b/haha.txt').remove()
    result = runner.invoke(['sync'])
    lines = result.output.splitlines()
    assert lines[0] == 'Syncing my_pair'
    assert lines[1].startswith('error: my_pair: '
                               'Storage "my_b" was completely emptied.')
    assert result.exception


def test_verbosity(tmpdir, runner):
    runner.write_with_general('')
    result = runner.invoke(['--verbosity=HAHA', 'sync'])
    assert result.exception
    assert 'invalid value for "--verbosity"' in result.output.lower()


def test_collections_cache_invalidation(tmpdir, runner):
    foo = tmpdir.mkdir('foo')
    bar = tmpdir.mkdir('bar')
    for x in 'abc':
        foo.mkdir(x)
        bar.mkdir(x)

    runner.write_with_general(dedent('''
    [storage foo]
    type = "filesystem"
    path = "{0}/foo/"
    fileext = ".txt"

    [storage bar]
    type = "filesystem"
    path = "{0}/bar/"
    fileext = ".txt"

    [pair foobar]
    a = "foo"
    b = "bar"
    collections = ["a", "b", "c"]
    ''').format(str(tmpdir)))

    foo.join('a/itemone.txt').write(format_item('itemone').raw)

    result = runner.invoke(['discover'])
    assert not result.exception

    result = runner.invoke(['sync'])
    assert not result.exception
    assert 'detected change in config file' not in result.output.lower()

    rv = bar.join('a').listdir()
    assert len(rv) == 1
    assert rv[0].basename == 'itemone.txt'

    runner.write_with_general(dedent('''
    [storage foo]
    type = "filesystem"
    path = "{0}/foo/"
    fileext = ".txt"

    [storage bar]
    type = "filesystem"
    path = "{0}/bar2/"
    fileext = ".txt"

    [pair foobar]
    a = "foo"
    b = "bar"
    collections = ["a", "b", "c"]
    ''').format(str(tmpdir)))

    for entry in tmpdir.join('status').listdir():
        if not str(entry).endswith('.collections'):
            entry.remove()
    bar2 = tmpdir.mkdir('bar2')
    for x in 'abc':
        bar2.mkdir(x)
    result = runner.invoke(['sync'])
    assert 'detected change in config file' in result.output.lower()
    assert result.exception

    result = runner.invoke(['discover'])
    assert not result.exception

    result = runner.invoke(['sync'])
    assert not result.exception

    rv = bar.join('a').listdir()
    rv2 = bar2.join('a').listdir()
    assert len(rv) == len(rv2) == 1
    assert rv[0].basename == rv2[0].basename == 'itemone.txt'


def test_invalid_pairs_as_cli_arg(tmpdir, runner):
    runner.write_with_general(dedent('''
    [storage foo]
    type = "filesystem"
    path = "{0}/foo/"
    fileext = ".txt"

    [storage bar]
    type = "filesystem"
    path = "{0}/bar/"
    fileext = ".txt"

    [pair foobar]
    a = "foo"
    b = "bar"
    collections = ["a", "b", "c"]
    ''').format(str(tmpdir)))

    for base in ('foo', 'bar'):
        base = tmpdir.mkdir(base)
        for c in 'abc':
            base.mkdir(c)

    result = runner.invoke(['discover'])
    assert not result.exception

    result = runner.invoke(['sync', 'foobar/d'])
    assert result.exception
    assert 'pair foobar: collection "d" not found' in result.output.lower()


def test_multiple_pairs(tmpdir, runner):
    def get_cfg():
        for name_a, name_b in ('foo', 'bar'), ('bam', 'baz'):
            yield dedent('''
            [pair {a}{b}]
            a = "{a}"
            b = "{b}"
            collections = null
            ''').format(a=name_a, b=name_b)

            for name in name_a, name_b:
                yield dedent('''
                [storage {name}]
                type = "filesystem"
                path = "{path}"
                fileext = ".txt"
                ''').format(name=name, path=str(tmpdir.mkdir(name)))

    runner.write_with_general(''.join(get_cfg()))

    result = runner.invoke(['discover'])
    assert not result.exception
    assert set(result.output.splitlines()) > set([
        'Discovering collections for pair bambaz',
        'Discovering collections for pair foobar'
    ])

    result = runner.invoke(['sync'])
    assert not result.exception
    assert set(result.output.splitlines()) == set([
        'Syncing bambaz',
        'Syncing foobar',
    ])


# XXX: https://github.com/pimutils/vdirsyncer/issues/617
@pytest.mark.xfail(sys.platform == 'darwin',
                   reason='This test inexplicably fails')
@pytest.mark.parametrize('collections', [
    {'persönlich'},
    {'a', 'A'},
    {'\ufffe'},
])
def test_create_collections(subtest, collections):

    @subtest
    def test_inner(tmpdir, runner):
        runner.write_with_general(dedent('''
        [pair foobar]
        a = "foo"
        b = "bar"
        collections = {colls}

        [storage foo]
        type = "filesystem"
        path = "{base}/foo/"
        fileext = ".txt"

        [storage bar]
        type = "filesystem"
        path = "{base}/bar/"
        fileext = ".txt"
        '''.format(base=str(tmpdir), colls=json.dumps(list(collections)))))

        result = runner.invoke(
            ['discover'],
            input='y\n' * 2 * (len(collections) + 1)
        )
        assert not result.exception, result.output

        result = runner.invoke(
            ['sync'] + ['foobar/' + x for x in collections]
        )
        assert not result.exception, result.output

        assert set(x.basename for x in tmpdir.join('foo').listdir()) == \
            set(x.basename for x in tmpdir.join('bar').listdir())


def test_ident_conflict(tmpdir, runner):
    runner.write_with_general(dedent('''
    [pair foobar]
    a = "foo"
    b = "bar"
    collections = null

    [storage foo]
    type = "filesystem"
    path = "{base}/foo/"
    fileext = ".txt"

    [storage bar]
    type = "filesystem"
    path = "{base}/bar/"
    fileext = ".txt"
    '''.format(base=str(tmpdir))))

    foo = tmpdir.mkdir('foo')
    tmpdir.mkdir('bar')

    item = format_item('1')
    foo.join('one.txt').write(item.raw)
    foo.join('two.txt').write(item.raw)
    foo.join('three.txt').write(item.raw)

    result = runner.invoke(['discover'])
    assert not result.exception

    result = runner.invoke(['sync'])
    assert result.exception
    assert ('error: foobar: Storage "foo" contains multiple items with the '
            'same UID or even content') in result.output
    assert sorted([
        'one.txt' in result.output,
        'two.txt' in result.output,
        'three.txt' in result.output,
    ]) == [False, True, True]


@pytest.mark.parametrize('existing,missing', [
    ('foo', 'bar'),
    ('bar', 'foo'),
])
def test_unknown_storage(tmpdir, runner, existing, missing):
    runner.write_with_general(dedent('''
    [pair foobar]
    a = "foo"
    b = "bar"
    collections = null

    [storage {existing}]
    type = "filesystem"
    path = "{base}/{existing}/"
    fileext = ".txt"
    '''.format(base=str(tmpdir), existing=existing)))

    tmpdir.mkdir(existing)

    result = runner.invoke(['discover'])
    assert result.exception

    assert (
        "Storage '{missing}' not found. "
        "These are the configured storages: ['{existing}']"
        .format(missing=missing, existing=existing)
    ) in result.output


@pytest.mark.parametrize('cmd', ['sync', 'metasync'])
def test_no_configured_pairs(tmpdir, runner, cmd):
    runner.write_with_general('')

    result = runner.invoke([cmd])
    assert result.output == 'critical: Nothing to do.\n'
    assert result.exception.code == 5


def test_conflict_resolution(tmpdir, runner):
    item_a = format_item('lol')
    item_b = format_item('lol')

    runner.write_with_general(dedent('''
    [pair foobar]
    a = "foo"
    b = "bar"
    collections = null
    conflict_resolution = ["command", "cp"]

    [storage foo]
    type = "filesystem"
    fileext = ".txt"
    path = "{base}/foo"

    [storage bar]
    type = "filesystem"
    fileext = ".txt"
    path = "{base}/bar"
    '''.format(base=str(tmpdir))))

    foo = tmpdir.join('foo')
    bar = tmpdir.join('bar')
    fooitem = foo.join('lol.txt').ensure()
    fooitem.write(item_a.raw)
    baritem = bar.join('lol.txt').ensure()
    baritem.write(item_b.raw)

    r = runner.invoke(['discover'])
    assert not r.exception

    r = runner.invoke(['sync'])
    assert not r.exception

    assert fooitem.read().splitlines() == item_a.raw.splitlines()
    assert baritem.read().splitlines() == item_a.raw.splitlines()


@pytest.mark.parametrize('partial_sync', ['error', 'ignore', 'revert', None])
def test_partial_sync(tmpdir, runner, partial_sync):
    runner.write_with_general(dedent('''
    [pair foobar]
    a = "foo"
    b = "bar"
    collections = null
    {partial_sync}

    [storage foo]
    type = "filesystem"
    fileext = ".txt"
    path = "{base}/foo"

    [storage bar]
    type = "filesystem"
    read_only = true
    fileext = ".txt"
    path = "{base}/bar"
    '''.format(
        partial_sync=('partial_sync = "{}"\n'.format(partial_sync)
                      if partial_sync else ''),
        base=str(tmpdir)
    )))

    foo = tmpdir.mkdir('foo')
    bar = tmpdir.mkdir('bar')

    item = format_item('other')
    foo.join('other.txt').write(item.raw)
    bar.join('other.txt').write(item.raw)

    baritem = bar.join('lol.txt')
    baritem.write(format_item('lol').raw)

    r = runner.invoke(['discover'])
    assert not r.exception

    r = runner.invoke(['sync'])
    assert not r.exception

    fooitem = foo.join('lol.txt')
    fooitem.remove()

    r = runner.invoke(['sync'])

    if partial_sync == 'error':
        assert r.exception
        assert 'Attempted change' in r.output
    elif partial_sync == 'ignore':
        assert baritem.exists()
        r = runner.invoke(['sync'])
        assert not r.exception
        assert baritem.exists()
    else:
        assert baritem.exists()
        r = runner.invoke(['sync'])
        assert not r.exception
        assert baritem.exists()
        assert fooitem.exists()


def test_fetch_only_necessary_params(tmpdir, runner):
    fetched_file = tmpdir.join('fetched_flag')
    fetch_script = tmpdir.join('fetch_script')
    fetch_script.write(dedent('''
    set -e
    touch "{}"
    echo ".txt"
    '''.format(str(fetched_file))))

    runner.write_with_general(dedent('''
    [pair foobar]
    a = "foo"
    b = "bar"
    collections = null

    [pair bambar]
    a = "bam"
    b = "bar"
    collections = null

    [storage foo]
    type = "filesystem"
    path = "{path}"
    fileext = ".txt"

    [storage bar]
    type = "filesystem"
    path = "{path}"
    fileext = ".txt"

    [storage bam]
    type = "filesystem"
    path = "{path}"
    fileext.fetch = ["command", "sh", "{script}"]
    '''.format(path=str(tmpdir.mkdir('bogus')), script=str(fetch_script))))

    def fetched():
        try:
            fetched_file.remove()
            return True
        except Exception:
            return False

    r = runner.invoke(['discover'])
    assert not r.exception
    assert fetched()

    r = runner.invoke(['sync', 'foobar'])
    assert not r.exception
    assert not fetched()

    r = runner.invoke(['sync'])
    assert not r.exception
    assert fetched()

    r = runner.invoke(['sync', 'bambar'])
    assert not r.exception
    assert fetched()
