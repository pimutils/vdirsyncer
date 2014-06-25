# -*- coding: utf-8 -*-
'''
    tests.test_cli
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''
from textwrap import dedent

from click.testing import CliRunner

import vdirsyncer.cli as cli


def test_load_config(tmpdir, monkeypatch):
    f = tmpdir.join('test.cfg')
    f.write(dedent('''
        [general]
        status_path = ~/.vdirsyncer/status/
        foo = 1

        [pair bob]
        a = bob_a
        b = bob_b
        foo = bar
        bam = true

        [storage bob_a]
        type = filesystem
        path = ~/.contacts/
        fileext = .vcf
        yesno = off
        number = 42

        [storage bob_b]
        type = carddav

        [bogus]
        lol = true
        ''').strip())

    fname = str(tmpdir) + '/test.cfg'
    errors = []
    monkeypatch.setattr('vdirsyncer.cli.cli_logger.error', errors.append)
    general, pairs, storages = cli.load_config(fname, pair_options=('bam',))
    assert general == {'foo': 1, 'status_path': '~/.vdirsyncer/status/'}
    assert pairs == {'bob': ('bob_a', 'bob_b', {'bam': True}, {'foo': 'bar'})}
    assert storages == {
        'bob_a': {'type': 'filesystem', 'path': '~/.contacts/',
                  'fileext': '.vcf', 'yesno': False, 'number': 42},
        'bob_b': {'type': 'carddav'}
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
    assert cli.storage_instance_from_config(config) == 'OK'


def test_expand_collection(monkeypatch):
    x = lambda *a: list(cli.expand_collection(*a))
    assert x(None, 'foo', None, None) == ['foo']
    assert x(None, 'from lol', None, None) == ['from lol']

    all_pairs = {'mypair': ('my_a', 'my_b', None, {'lol': True})}
    all_storages = {'my_a': {'type': 'mytype_a', 'is_a': True},
                    'my_b': {'type': 'mytype_b', 'is_b': True}}

    class TypeA(object):
        @classmethod
        def discover(cls, **config):
            assert config == {
                'is_a': True,
                'lol': True
            }
            for i in range(1, 4):
                s = cls()
                s.collection = 'a{}'.format(i)
                yield s

    class TypeB(object):
        @classmethod
        def discover(cls, **config):
            assert config == {
                'is_b': True,
                'lol': True
            }
            for i in range(1, 4):
                s = cls()
                s.collection = 'b{}'.format(i)
                yield s

    import vdirsyncer.storage
    monkeypatch.setitem(vdirsyncer.storage.storage_names, 'mytype_a', TypeA)
    monkeypatch.setitem(vdirsyncer.storage.storage_names, 'mytype_b', TypeB)

    assert x('mypair', 'mycoll', all_pairs, all_storages) == ['mycoll']
    assert x('mypair', 'from a', all_pairs, all_storages) == ['a1', 'a2', 'a3']
    assert x('mypair', 'from b', all_pairs, all_storages) == ['b1', 'b2', 'b3']


def test_parse_pairs_args():
    pairs = {
        'foo': ('bar', 'baz', {'conflict_resolution': 'a wins'},
                {'storage_option': True}),
        'one': ('two', 'three', {'collections': 'a,b,c'}, {}),
        'eins': ('zwei', 'drei', {'ha': True}, {})
    }
    assert list(
        cli.parse_pairs_args(['foo/foocoll', 'one', 'eins'], pairs)
    ) == [
        ('foo', 'foocoll'),
        ('one', 'a'),
        ('one', 'b'),
        ('one', 'c'),
        ('eins', None)
    ]


def test_simple_run(tmpdir):
    config_file = tmpdir.join('config')
    config_file.write(dedent('''
    [general]
    status_path = {0}/status/

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

    runner = CliRunner(env={'VDIRSYNCER_CONFIG': str(config_file)})
    result = runner.invoke(cli.app, ['sync'])
    assert not result.exception
    assert result.output.lower().strip() == 'syncing my_pair'

    tmpdir.join('path_a/haha.txt').write('UID:haha')
    result = runner.invoke(cli.app, ['sync'])
    assert tmpdir.join('path_b/haha.txt').read() == 'UID:haha'


def test_missing_general_section(tmpdir):
    config_file = tmpdir.join('config')
    config_file.write(dedent('''
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

    runner = CliRunner()
    result = runner.invoke(
        cli.app, ['sync'],
        env={'VDIRSYNCER_CONFIG': str(config_file)}
    )
    assert result.exception
    assert 'critical: unable to find general section' in result.output.lower()


def test_verbosity(tmpdir):
    runner = CliRunner()
    config_file = tmpdir.join('config')
    config_file.write(dedent('''
    [general]
    status_path = {0}/status/
    ''').format(str(tmpdir)))

    result = runner.invoke(
        cli.app, ['--verbosity=HAHA', 'sync'],
        env={'VDIRSYNCER_CONFIG': str(config_file)}
    )
    assert result.exception
    assert 'invalid verbosity value' in result.output.lower()
