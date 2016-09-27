
from hypothesis import given, settings


from vdirsyncer.repair import repair_storage
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.utils import href_safe
from vdirsyncer.utils.vobject import Item

from . import uid_strategy


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
