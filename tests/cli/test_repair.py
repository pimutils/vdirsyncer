from textwrap import dedent

from vdirsyncer.cli.utils import repair_storage
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.utils.vobject import Item


def test_repair_uids():
    s = MemoryStorage()
    s.upload(Item(u'BEGIN:VCARD\nEND:VCARD'))

    repair_storage(s)

    uid, = [s.get(href)[0].uid for href, etag in s.list()]
    s.upload(Item(u'BEGIN:VCARD\nUID:{}\nEND:VCARD'.format(uid)))

    uid1, uid2 = [s.get(href)[0].uid for href, etag in s.list()]
    assert uid1 == uid2

    repair_storage(s)

    uid1, uid2 = [s.get(href)[0].uid for href, etag in s.list()]
    assert uid1 != uid2


def test_full(tmpdir, runner):
    runner.write_with_general(dedent('''
        [storage foo]
        type = filesystem
        path = {0}/foo/
        fileext = .txt
        ''').format(str(tmpdir)))

    foo = tmpdir.mkdir('foo')

    result = runner.invoke(['repair', 'foo'])
    assert not result.exception

    foo.join('item.txt').write('BEGIN:VCARD\nEND:VCARD')
    foo.join('toobroken.txt').write('')

    result = runner.invoke(['repair', 'foo'])
    assert not result.exception
    assert 'No UID' in result.output
    assert 'warning: Item toobroken.txt can\'t be parsed, skipping' \
        in result.output
    assert 'UID:' in foo.join('item.txt').read()
