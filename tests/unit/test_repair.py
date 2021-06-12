import pytest
from hypothesis import given
from hypothesis import HealthCheck
from hypothesis import settings

from tests import uid_strategy
from vdirsyncer.repair import IrreparableItem
from vdirsyncer.repair import repair_item
from vdirsyncer.repair import repair_storage
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.utils import href_safe
from vdirsyncer.vobject import Item


@given(uid=uid_strategy)
# Using the random module for UIDs:
@settings(suppress_health_check=HealthCheck.all())
def test_repair_uids(uid):
    s = MemoryStorage()
    s.items = {
        "one": ("asdf", Item(f"BEGIN:VCARD\nFN:Hans\nUID:{uid}\nEND:VCARD")),
        "two": ("asdf", Item(f"BEGIN:VCARD\nFN:Peppi\nUID:{uid}\nEND:VCARD")),
    }

    uid1, uid2 = [s.get(href)[0].uid for href, etag in s.list()]
    assert uid1 == uid2

    repair_storage(s, repair_unsafe_uid=False)

    uid1, uid2 = [s.get(href)[0].uid for href, etag in s.list()]
    assert uid1 != uid2


@given(uid=uid_strategy.filter(lambda x: not href_safe(x)))
# Using the random module for UIDs:
@settings(suppress_health_check=HealthCheck.all())
def test_repair_unsafe_uids(uid):
    s = MemoryStorage()
    item = Item(f"BEGIN:VCARD\nUID:{uid}\nEND:VCARD")
    href, etag = s.upload(item)
    assert s.get(href)[0].uid == uid
    assert not href_safe(uid)

    repair_storage(s, repair_unsafe_uid=True)

    new_href = list(s.list())[0][0]
    assert href_safe(new_href)
    newuid = s.get(new_href)[0].uid
    assert href_safe(newuid)


@pytest.mark.parametrize(
    "uid,href", [("b@dh0mbr3", "perfectly-fine"), ("perfectly-fine", "b@dh0mbr3")]
)
def test_repair_unsafe_href(uid, href):
    item = Item(f"BEGIN:VCARD\nUID:{uid}\nEND:VCARD")
    new_item = repair_item(href, item, set(), True)
    assert new_item.raw != item.raw
    assert new_item.uid != item.uid
    assert href_safe(new_item.uid)


def test_repair_do_nothing():
    item = Item("BEGIN:VCARD\nUID:justfine\nEND:VCARD")
    assert repair_item("fine", item, set(), True) is item
    assert repair_item("@@@@/fine", item, set(), True) is item


@pytest.mark.parametrize(
    "raw", ["AYYY", "", "@@@@", "BEGIN:VCARD", "BEGIN:FOO\nEND:FOO"]
)
def test_repair_irreparable(raw):
    with pytest.raises(IrreparableItem):
        repair_item("fine", Item(raw), set(), True)
