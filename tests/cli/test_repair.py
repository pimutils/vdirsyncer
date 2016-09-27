# encoding: utf-8

import pytest

from textwrap import dedent

from hypothesis import given, settings

from tests import uid_strategy

from vdirsyncer.repair import repair_storage
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.utils import href_safe
from vdirsyncer.utils.vobject import Item


@given(uid=uid_strategy)
@settings(perform_health_check=False)  # Using the random module for UIDs
def test_repair_uids(uid):
    s = MemoryStorage()
    s.items = {
        'one': (
            'asdf',
            Item(u'BEGIN:VCARD\nFN:Hans\nUID:{}\nEND:VCARD'.format(uid))
        ),
        'two': (
            'asdf',
            Item(u'BEGIN:VCARD\nFN:Peppi\nUID:{}\nEND:VCARD'.format(uid))
        )
    }

    uid1, uid2 = [s.get(href)[0].uid for href, etag in s.list()]
    assert uid1 == uid2

    repair_storage(s)

    uid1, uid2 = [s.get(href)[0].uid for href, etag in s.list()]
    assert uid1 != uid2


@given(uid=uid_strategy.filter(lambda x: not href_safe(x)))
@settings(perform_health_check=False)  # Using the random module for UIDs
def test_repair_unsafe_uids(uid):
    s = MemoryStorage()
    item = Item(u'BEGIN:VCARD\nUID:{}\nEND:VCARD'.format(uid))
    print(repr(item.raw))
    href, etag = s.upload(item)
    assert s.get(href)[0].uid == uid
    assert not href_safe(uid)

    repair_storage(s)

    new_href = list(s.list())[0][0]
    assert href_safe(new_href)
    newuid = s.get(new_href)[0].uid
    assert href_safe(newuid)


@pytest.mark.parametrize('collection', [None, "foocoll"])
def test_full(tmpdir, runner, collection):
    runner.write_with_general(dedent('''
        [storage foo]
        type = filesystem
        path = {base}/foo/
        fileext = .txt
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
