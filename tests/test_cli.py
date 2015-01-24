# -*- coding: utf-8 -*-

import io
from textwrap import dedent

from click.testing import CliRunner

import pytest

import vdirsyncer.cli as cli


class _CustomRunner(object):
    def __init__(self, tmpdir):
        self.tmpdir = tmpdir
        self.cfg = tmpdir.join('config')
        self.runner = CliRunner()

    def invoke(self, args, env=None, **kwargs):
        env = env or {}
        env.setdefault('VDIRSYNCER_CONFIG', str(self.cfg))
        return self.runner.invoke(cli.app, args, env=env, **kwargs)

    def write_with_general(self, data):
        self.cfg.write(dedent('''
        [general]
        status_path = {}/status/
        ''').format(str(self.tmpdir)))
        self.cfg.write(data, mode='a')


@pytest.fixture
def runner(tmpdir, monkeypatch):
    return _CustomRunner(tmpdir)


def test_read_config(monkeypatch):
    f = io.StringIO(dedent(u'''
        [general]
        status_path = /tmp/status/

        [pair bob]
        a = bob_a
        b = bob_b
        foo = bar
        bam = true

        [storage bob_a]
        type = filesystem
        path = /tmp/contacts/
        fileext = .vcf
        yesno = false
        number = 42

        [storage bob_b]
        type = carddav

        [bogus]
        lol = true
        '''))

    errors = []
    monkeypatch.setattr('vdirsyncer.cli.cli_logger.error', errors.append)
    general, pairs, storages = cli.utils.read_config(f)
    assert general == {'status_path': '/tmp/status/'}
    assert pairs == {'bob': ('bob_a', 'bob_b', {'bam': True, 'foo': 'bar'})}
    assert storages == {
        'bob_a': {'type': 'filesystem', 'path': '/tmp/contacts/', 'fileext':
                  '.vcf', 'yesno': False, 'number': 42,
                  'instance_name': 'bob_a'},
        'bob_b': {'type': 'carddav', 'instance_name': 'bob_b'}
    }

    assert len(errors) == 1
    assert errors[0].startswith('Unknown section')
    assert 'bogus' in errors[0]


def test_storage_instance_from_config(monkeypatch):
    def lol(**kw):
        assert kw == {'foo': 'bar', 'baz': 1}
        return 'OK'

    import vdirsyncer.storage
    monkeypatch.setitem(vdirsyncer.storage.storage_names, 'lol', lol)
    config = {'type': 'lol', 'foo': 'bar', 'baz': 1}
    assert cli.utils.storage_instance_from_config(config) == 'OK'


def test_parse_pairs_args():
    pairs = {
        'foo': ('bar', 'baz', {'conflict_resolution': 'a wins'},
                {'storage_option': True}),
        'one': ('two', 'three', {'collections': 'a,b,c'}, {}),
        'eins': ('zwei', 'drei', {'ha': True}, {})
    }
    assert sorted(
        cli.parse_pairs_args(['foo/foocoll', 'one', 'eins'], pairs)
    ) == [
        ('eins', set()),
        ('foo', {'foocoll'}),
        ('one', set()),
    ]


def test_simple_run(tmpdir, runner):
    runner.write_with_general(dedent('''
    [pair my_pair]
    a = my_a
    b = my_b

    [storage my_a]
    type = filesystem
    path = {0}/path_a/
    fileext = .txt

    [storage my_b]
    type = filesystem
    path = {0}/path_b/
    fileext = .txt
    ''').format(str(tmpdir)))

    tmpdir.mkdir('path_a')
    tmpdir.mkdir('path_b')

    result = runner.invoke(['sync'])
    assert not result.exception

    tmpdir.join('path_a/haha.txt').write('UID:haha')
    result = runner.invoke(['sync'])
    assert 'Copying (uploading) item haha to my_b' in result.output
    assert tmpdir.join('path_b/haha.txt').read() == 'UID:haha'


def test_empty_storage(tmpdir, runner):
    runner.write_with_general(dedent('''
    [pair my_pair]
    a = my_a
    b = my_b

    [storage my_a]
    type = filesystem
    path = {0}/path_a/
    fileext = .txt

    [storage my_b]
    type = filesystem
    path = {0}/path_b/
    fileext = .txt
    ''').format(str(tmpdir)))

    tmpdir.mkdir('path_a')
    tmpdir.mkdir('path_b')

    result = runner.invoke(['sync'])
    assert not result.exception

    tmpdir.join('path_a/haha.txt').write('UID:haha')
    result = runner.invoke(['sync'])
    tmpdir.join('path_b/haha.txt').remove()
    result = runner.invoke(['sync'])
    lines = result.output.splitlines()
    assert len(lines) == 2
    assert lines[0] == 'Syncing my_pair'
    assert lines[1].startswith('error: my_pair: '
                               'Storage "my_b" was completely emptied.')
    assert result.exception


def test_missing_general_section(tmpdir, runner):
    runner.cfg.write(dedent('''
    [pair my_pair]
    a = my_a
    b = my_b

    [storage my_a]
    type = filesystem
    path = {0}/path_a/
    fileext = .txt

    [storage my_b]
    type = filesystem
    path = {0}/path_b/
    fileext = .txt
    ''').format(str(tmpdir)))

    result = runner.invoke(['sync'])
    assert result.exception
    assert result.output.startswith('critical:')
    assert 'invalid general section' in result.output.lower()


def test_wrong_general_section(tmpdir, runner):
    runner.cfg.write(dedent('''
    [general]
    wrong = true
    '''))
    result = runner.invoke(['sync'])

    assert result.exception
    lines = result.output.splitlines()
    assert lines[:-2] == [
        'critical: general section doesn\'t take the parameters: wrong',
        'critical: general section is missing the parameters: status_path'
    ]
    assert 'Invalid general section.' in lines[-2]


def test_verbosity(tmpdir):
    runner = CliRunner()
    config_file = tmpdir.join('config')
    config_file.write('')

    result = runner.invoke(
        cli.app, ['--verbosity=HAHA', 'sync'],
        env={'VDIRSYNCER_CONFIG': str(config_file)}
    )
    assert result.exception
    assert 'invalid verbosity value' in result.output.lower()


def test_invalid_storage_name():
    f = io.StringIO(dedent(u'''
        [general]
        status_path = /tmp/status/

        [storage foo.bar]
        '''))

    with pytest.raises(cli.CliError) as excinfo:
        cli.utils.read_config(f)

    assert 'invalid characters' in str(excinfo.value).lower()


def test_deprecated_item_status(tmpdir):
    f = tmpdir.join('mypair.items')
    f.write(dedent('''
    ["ident", ["href_a", "etag_a", "href_b", "etag_b"]]
    ["ident_two", ["href_a", "etag_a", "href_b", "etag_b"]]
    ''').strip())

    data = {
        'ident': ['href_a', 'etag_a', 'href_b', 'etag_b'],
        'ident_two': ['href_a', 'etag_a', 'href_b', 'etag_b']
    }

    assert cli.utils.load_status(
        str(tmpdir), 'mypair', data_type='items') == data

    cli.utils.save_status(
        str(tmpdir), 'mypair', data_type='items', data=data)
    assert cli.utils.load_status(
        str(tmpdir), 'mypair', data_type='items') == data


def test_collections_cache_invalidation(tmpdir, runner):
    runner.write_with_general(dedent('''
    [storage foo]
    type = filesystem
    path = {0}/foo/
    fileext = .txt

    [storage bar]
    type = filesystem
    path = {0}/bar/
    fileext = .txt

    [pair foobar]
    a = foo
    b = bar
    collections = ["a", "b", "c"]
    ''').format(str(tmpdir)))

    foo = tmpdir.mkdir('foo')
    bar = tmpdir.mkdir('bar')
    for x in 'abc':
        foo.mkdir(x)
        bar.mkdir(x)
    foo.join('a/itemone.txt').write('UID:itemone')

    result = runner.invoke(['sync'])
    assert not result.exception

    rv = bar.join('a').listdir()
    assert len(rv) == 1
    assert rv[0].basename == 'itemone.txt'

    runner.write_with_general(dedent('''
    [storage foo]
    type = filesystem
    path = {0}/foo/
    fileext = .txt

    [storage bar]
    type = filesystem
    path = {0}/bar2/
    fileext = .txt

    [pair foobar]
    a = foo
    b = bar
    collections = ["a", "b", "c"]
    ''').format(str(tmpdir)))

    tmpdir.join('status').remove()
    bar2 = tmpdir.mkdir('bar2')
    for x in 'abc':
        bar2.mkdir(x)
    result = runner.invoke(['sync'])
    assert not result.exception

    rv = bar.join('a').listdir()
    rv2 = bar2.join('a').listdir()
    assert len(rv) == len(rv2) == 1
    assert rv[0].basename == rv2[0].basename == 'itemone.txt'


def test_invalid_pairs_as_cli_arg(tmpdir, runner):
    runner.write_with_general(dedent('''
    [storage foo]
    type = filesystem
    path = {0}/foo/
    fileext = .txt

    [storage bar]
    type = filesystem
    path = {0}/bar/
    fileext = .txt

    [pair foobar]
    a = foo
    b = bar
    collections = ["a", "b", "c"]
    ''').format(str(tmpdir)))

    for base in ('foo', 'bar'):
        base = tmpdir.mkdir(base)
        for c in 'abc':
            base.mkdir(c)

    result = runner.invoke(['sync', 'foobar/d'])
    assert result.exception
    assert 'pair foobar: collection d not found' in result.output.lower()


def test_discover_command(tmpdir, runner):
    runner.write_with_general(dedent('''
    [storage foo]
    type = filesystem
    path = {0}/foo/
    fileext = .txt

    [storage bar]
    type = filesystem
    path = {0}/bar/
    fileext = .txt

    [pair foobar]
    a = foo
    b = bar
    collections = ["from a"]
    ''').format(str(tmpdir)))

    foo = tmpdir.mkdir('foo')
    bar = tmpdir.mkdir('bar')

    for x in 'abc':
        foo.mkdir(x)
        bar.mkdir(x)
    bar.mkdir('d')

    result = runner.invoke(['sync'])
    assert not result.exception
    lines = result.output.splitlines()
    assert lines[0].startswith('Discovering')
    assert 'Syncing foobar/a' in lines
    assert 'Syncing foobar/b' in lines
    assert 'Syncing foobar/c' in lines
    assert 'Syncing foobar/d' not in lines

    foo.mkdir('d')
    result = runner.invoke(['sync'])
    assert not result.exception
    assert 'Syncing foobar/a' in lines
    assert 'Syncing foobar/b' in lines
    assert 'Syncing foobar/c' in lines
    assert 'Syncing foobar/d' not in result.output

    result = runner.invoke(['discover'])
    assert not result.exception

    result = runner.invoke(['sync'])
    assert not result.exception
    assert 'Syncing foobar/a' in lines
    assert 'Syncing foobar/b' in lines
    assert 'Syncing foobar/c' in lines
    assert 'Syncing foobar/d' in result.output


def test_multiple_pairs(tmpdir, runner):
    def get_cfg():
        for name_a, name_b in ('foo', 'bar'), ('bam', 'baz'):
            yield dedent('''
            [pair {a}{b}]
            a = {a}
            b = {b}
            ''').format(a=name_a, b=name_b)

            for name in name_a, name_b:
                yield dedent('''
                [storage {name}]
                type = filesystem
                path = {base}/{name}/
                fileext = .txt
                ''').format(name=name, base=str(tmpdir))

    runner.write_with_general(''.join(get_cfg()))

    result = runner.invoke(['sync'])
    assert set(result.output.splitlines()) > set([
        'Discovering collections for pair bambaz',
        'Discovering collections for pair foobar',
        'Syncing bambaz',
        'Syncing foobar',
    ])


def test_invalid_collections_arg(tmpdir, runner):
    runner.write_with_general(dedent('''
    [pair foobar]
    a = foo
    b = bar
    collections = [null]

    [storage foo]
    type = filesystem
    path = {base}/foo/
    fileext = .txt

    [storage bar]
    type = filesystem
    path = {base}/bar/
    fileext = .txt
    '''.format(base=str(tmpdir))))

    result = runner.invoke(['sync'])
    assert result.exception
    assert result.output.strip().endswith(
        'Section `pair foobar`: `collections` parameter must be a list of '
        'collection names (strings!) or `null`.'
    )


def test_create_collections(tmpdir, runner):
    runner.write_with_general(dedent('''
    [pair foobar]
    a = foo
    b = bar
    collections = ["a", "b", "c"]

    [storage foo]
    type = filesystem
    path = {base}/foo/
    fileext = .txt

    [storage bar]
    type = filesystem
    path = {base}/bar/
    fileext = .txt
    '''.format(base=str(tmpdir))))

    result = runner.invoke(['sync'])
    assert result.exception
    entries = set(x.basename for x in tmpdir.listdir())
    assert 'foo' not in entries and 'bar' not in entries

    result = runner.invoke(['sync'], input='y\n' * 6)
    assert not result.exception
    assert \
        set(x.basename for x in tmpdir.join('foo').listdir()) == \
        set(x.basename for x in tmpdir.join('bar').listdir()) == \
        set('abc')


def test_ident_conflict(tmpdir, runner):
    runner.write_with_general(dedent('''
    [pair foobar]
    a = foo
    b = bar

    [storage foo]
    type = filesystem
    path = {base}/foo/
    fileext = .txt

    [storage bar]
    type = filesystem
    path = {base}/bar/
    fileext = .txt
    '''.format(base=str(tmpdir))))

    foo = tmpdir.mkdir('foo')
    tmpdir.mkdir('bar')

    foo.join('one.txt').write('UID:1')
    foo.join('two.txt').write('UID:1')
    foo.join('three.txt').write('UID:1')

    result = runner.invoke(['sync'])
    assert result.exception
    assert ('error: foobar: Storage "foo" contains multiple items with the '
            'same UID or even content') in result.output
    assert sorted([
        'one.txt' in result.output,
        'two.txt' in result.output,
        'three.txt' in result.output,
    ]) == [False, True, True]


def test_parse_config_value(capsys):
    invalid = object()

    def x(s):
        try:
            rv = cli.utils.parse_config_value(s)
        except ValueError:
            return invalid
        else:
            warnings = capsys.readouterr()[1]
            return rv, len(warnings.splitlines())

    assert x('123  # comment!') is invalid

    assert x('True') == ('True', 1)
    assert x('False') == ('False', 1)
    assert x('Yes') == ('Yes', 1)
    assert x('None') == ('None', 1)
    assert x('"True"') == ('True', 0)
    assert x('"False"') == ('False', 0)

    assert x('"123  # comment!"') == ('123  # comment!', 0)
    assert x('true') == (True, 0)
    assert x('false') == (False, 0)
    assert x('null') == (None, 0)
    assert x('3.14') == (3.14, 0)
    assert x('') == ('', 0)
    assert x('""') == ('', 0)
