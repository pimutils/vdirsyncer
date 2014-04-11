# -*- coding: utf-8 -*-
'''
    tests.test_cli
    ~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''
from textwrap import dedent

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
