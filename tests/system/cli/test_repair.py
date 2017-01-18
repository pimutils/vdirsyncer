# encoding: utf-8

from textwrap import dedent

import pytest


@pytest.mark.parametrize('collection', [None, "foocoll"])
def test_full(tmpdir, runner, collection):
    runner.write_with_general(dedent('''
        [storage foo]
        type = "filesystem"
        path = "{base}/foo/"
        fileext = ".txt"
        ''').format(base=str(tmpdir)))

    storage = tmpdir.mkdir('foo')
    if collection is not None:
        storage = storage.mkdir(collection)
        collection_arg = 'foo/{}'.format(collection)
    else:
        collection_arg = 'foo'

    argv = ['repair', collection_arg]

    result = runner.invoke(argv, input='y')
    assert not result.exception

    storage.join('item.txt').write('BEGIN:VCARD\nEND:VCARD')
    storage.join('toobroken.txt').write('')

    result = runner.invoke(argv, input='y')
    assert not result.exception
    assert 'No UID' in result.output
    assert 'warning: Item toobroken.txt can\'t be parsed, skipping' \
        in result.output
    new_fname, = [x for x in storage.listdir() if 'toobroken' not in str(x)]
    assert 'UID:' in new_fname.read()
