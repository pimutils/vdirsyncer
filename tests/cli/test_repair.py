# encoding: utf-8

from textwrap import dedent

import pytest

from vdirsyncer.repair import repair_storage
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.utils import href_safe
from vdirsyncer.utils.vobject import Item


def test_repair_uids():
    s = MemoryStorage()
    s.items = {
        'one': ('asdf', Item(u'BEGIN:VCARD\nFN:Hans\nUID:asdf\nEND:VCARD')),
        'two': ('asdf', Item(u'BEGIN:VCARD\nFN:Peppi\nUID:asdf\nEND:VCARD'))
    }

    uid1, uid2 = [s.get(href)[0].uid for href, etag in s.list()]
    assert uid1 == uid2

    repair_storage(s)

    uid1, uid2 = [s.get(href)[0].uid for href, etag in s.list()]
    assert uid1 != uid2


@pytest.mark.parametrize('uid', [
    u'äää',
    u'test@foo',
    u'test foo',
])
def test_repair_unsafe_uids(uid):
    assert not href_safe(uid)

    s = MemoryStorage()
    href, etag = s.upload(Item(u'BEGIN:VCARD\nUID:{}\nEND:VCARD'.format(uid)))
    assert s.get(href)[0].uid == uid

    repair_storage(s)

    new_href = list(s.list())[0][0]
    assert href_safe(new_href)
    newuid = s.get(new_href)[0].uid
    assert href_safe(newuid)


def test_full(tmpdir, runner):
    runner.write_with_general(dedent('''
        [storage foo]
        type = filesystem
        path = {0}/foo/
        fileext = .txt
        ''').format(str(tmpdir)))

    foo = tmpdir.mkdir('foo')

    result = runner.invoke(['repair', 'foo'], input='y')
    assert not result.exception

    foo.join('item.txt').write('BEGIN:VCARD\nEND:VCARD')
    foo.join('toobroken.txt').write('')

    result = runner.invoke(['repair', 'foo'], input='y')
    assert not result.exception
    assert 'No UID' in result.output
    assert 'warning: Item toobroken.txt can\'t be parsed, skipping' \
        in result.output
    new_fname, = [x for x in foo.listdir() if 'toobroken' not in str(x)]
    assert 'UID:' in new_fname.read()
