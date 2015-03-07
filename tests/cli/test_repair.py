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
