import io
from textwrap import dedent

import pytest

import vdirsyncer.cli.utils  # noqa
from vdirsyncer import cli, exceptions
from vdirsyncer.cli.config import parse_config_value, \
    read_config as _read_config


@pytest.fixture
def read_config(tmpdir):
    def inner(cfg):
        f = io.StringIO(dedent(cfg.format(base=str(tmpdir))))
        return _read_config(f)
    return inner


def test_read_config(read_config, monkeypatch):
    errors = []
    monkeypatch.setattr('vdirsyncer.cli.cli_logger.error', errors.append)
    general, pairs, storages = read_config(u'''
        [general]
        status_path = /tmp/status/

        [pair bob]
        a = bob_a
        b = bob_b
        foo = bar
        bam = true
        collections = null

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
        ''')

    assert general == {'status_path': '/tmp/status/'}
    assert pairs == {'bob': ('bob_a', 'bob_b',
                             {'collections': None, 'bam': True, 'foo': 'bar'})}
    assert storages == {
        'bob_a': {'type': 'filesystem', 'path': '/tmp/contacts/', 'fileext':
                  '.vcf', 'yesno': False, 'number': 42,
                  'instance_name': 'bob_a'},
        'bob_b': {'type': 'carddav', 'instance_name': 'bob_b'}
    }

    assert len(errors) == 1
    assert errors[0].startswith('Unknown section')
    assert 'bogus' in errors[0]


def test_missing_collections_param(read_config, monkeypatch):
    errorlog = []
    monkeypatch.setattr('vdirsyncer.cli.cli_logger.error', errorlog.append)

    with pytest.raises(exceptions.UserError) as excinfo:
        read_config(u'''
            [general]
            status_path = /tmp/status/

            [pair bob]
            a = bob_a
            b = bob_b

            [storage bob_a]
            type = lmao

            [storage bob_b]
            type = lmao
            ''')

    assert 'collections parameter missing' in str(excinfo.value)
    assert not errorlog


def test_storage_instance_from_config(monkeypatch):
    def lol(**kw):
        assert kw == {'foo': 'bar', 'baz': 1}
        return 'OK'

    monkeypatch.setitem(cli.utils.storage_names._storages,
                        'lol', lol)
    config = {'type': 'lol', 'foo': 'bar', 'baz': 1}
    assert cli.utils.storage_instance_from_config(config) == 'OK'


def test_missing_general_section(read_config):
    with pytest.raises(exceptions.UserError) as excinfo:
        read_config(u'''
            [pair my_pair]
            a = my_a
            b = my_b
            collections = null

            [storage my_a]
            type = filesystem
            path = {base}/path_a/
            fileext = .txt

            [storage my_b]
            type = filesystem
            path = {base}/path_b/
            fileext = .txt
            ''')

    assert 'Invalid general section.' in str(excinfo.value)


def test_wrong_general_section(read_config):
    with pytest.raises(exceptions.UserError) as excinfo:
        read_config(u'''
            [general]
            wrong = true
            ''')

    assert 'Invalid general section.' in str(excinfo.value)
    assert excinfo.value.problems == [
        'general section doesn\'t take the parameters: wrong',
        'general section is missing the parameters: status_path'
    ]


def test_invalid_storage_name():
    f = io.StringIO(dedent(u'''
        [general]
        status_path = {base}/status/

        [storage foo.bar]
        '''))

    with pytest.raises(exceptions.UserError) as excinfo:
        _read_config(f)

    assert 'invalid characters' in str(excinfo.value).lower()


def test_parse_config_value(capsys):
    invalid = object()

    def x(s):
        try:
            rv = parse_config_value(s)
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


def test_invalid_collections_arg():
    f = io.StringIO(dedent(u'''
        [general]
        status_path = /tmp/status/

        [pair foobar]
        a = foo
        b = bar
        collections = [null]

        [storage foo]
        type = filesystem
        path = /tmp/foo/
        fileext = .txt

        [storage bar]
        type = filesystem
        path = /tmp/bar/
        fileext = .txt
        '''))

    with pytest.raises(exceptions.UserError) as excinfo:
        _read_config(f)

    assert (
        'Section `pair foobar`: `collections` parameter must be a list of '
        'collection names (strings!) or `null`.'
    ) in str(excinfo.value)
