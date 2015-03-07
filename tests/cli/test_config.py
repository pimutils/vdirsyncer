import io
from textwrap import dedent

import pytest

from vdirsyncer import cli


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


def test_invalid_storage_name():
    f = io.StringIO(dedent(u'''
        [general]
        status_path = /tmp/status/

        [storage foo.bar]
        '''))

    with pytest.raises(cli.CliError) as excinfo:
        cli.utils.read_config(f)

    assert 'invalid characters' in str(excinfo.value).lower()


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
