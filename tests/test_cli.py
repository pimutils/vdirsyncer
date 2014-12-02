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
    status_path = '{}/status/'.format(str(tmpdir))
    contacts_path = '{}/contacts/'.format(str(tmpdir))
    f.write(dedent('''
        [general]
        status_path = {status}

        [pair bob]
        a = bob_a
        b = bob_b
        foo = bar
        bam = true

        [storage bob_a]
        type = filesystem
        path = {contacts}
        fileext = .vcf
        yesno = off
        number = 42

        [storage bob_b]
        type = carddav

        [bogus]
        lol = true
        ''').strip().format(status=status_path, contacts=contacts_path))

    fname = str(tmpdir) + '/test.cfg'
    errors = []
    monkeypatch.setattr('vdirsyncer.cli.cli_logger.error', errors.append)
    general, pairs, storages = cli.load_config(fname, pair_options=('bam',))
    assert general == {'status_path': status_path}
    assert pairs == {'bob': ('bob_a', 'bob_b', {'bam': True}, {'foo': 'bar'})}
    assert storages == {
        'bob_a': {'type': 'filesystem', 'path': contacts_path, 'fileext':
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
    assert cli.storage_instance_from_config(config) == 'OK'


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
    assert result.output == ('Syncing my_pair\n'
                             'Copying (uploading) item haha to my_b\n')
    assert tmpdir.join('path_b/haha.txt').read() == 'UID:haha'

    result = runner.invoke(cli.app, ['sync', 'my_pair', 'my_pair'])
    assert set(result.output.splitlines()) == set([
        'Syncing my_pair',
        'warning: Already prepared my_pair, skipping'
    ])
    assert not result.exception


def test_empty_storage(tmpdir):
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
    tmpdir.join('path_b/haha.txt').remove()
    result = runner.invoke(cli.app, ['sync'])
    assert result.output.splitlines() == [
        'Syncing my_pair',
        'error: {status_name}: Storage "{name}" was completely emptied. Use '
        '"--force-delete {status_name}" to synchronize that emptyness to '
        'the other side, or delete the status by yourself to restore the '
        'items from the non-empty side.'.format(status_name='my_pair',
                                                name='my_b')
    ]
    assert result.exception


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
    assert result.output.startswith('critical:')
    assert 'unable to find general section' in result.output.lower()


def test_wrong_general_section(tmpdir):
    config_file = tmpdir.join('config')
    config_file.write(dedent('''
    [general]
    wrong = true
    '''))

    runner = CliRunner()
    result = runner.invoke(
        cli.app, ['sync'],
        env={'VDIRSYNCER_CONFIG': str(config_file)}
    )

    assert result.exception
    lines = result.output.splitlines()
    assert lines[:-1] == [
        'critical: general section doesn\'t take the parameters: wrong',
        'critical: general section is missing the parameters: status_path'
    ]
    assert lines[-1].startswith('critical:')
    assert lines[-1].endswith('Invalid general section.')


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
