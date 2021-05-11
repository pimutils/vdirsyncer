from copy import deepcopy

import hypothesis.strategies as st
import pytest
from hypothesis import assume
from hypothesis.stateful import Bundle
from hypothesis.stateful import rule
from hypothesis.stateful import RuleBasedStateMachine

from tests import blow_up
from tests import uid_strategy
from vdirsyncer.storage.memory import _random_string
from vdirsyncer.storage.memory import MemoryStorage
from vdirsyncer.sync import sync as _sync
from vdirsyncer.sync.exceptions import BothReadOnly
from vdirsyncer.sync.exceptions import IdentConflict
from vdirsyncer.sync.exceptions import PartialSync
from vdirsyncer.sync.exceptions import StorageEmpty
from vdirsyncer.sync.exceptions import SyncConflict
from vdirsyncer.sync.status import SqliteStatus
from vdirsyncer.vobject import Item


def sync(a, b, status, *args, **kwargs):
    new_status = SqliteStatus(":memory:")
    new_status.load_legacy_status(status)
    rv = _sync(a, b, new_status, *args, **kwargs)
    status.clear()
    status.update(new_status.to_legacy_status())
    return rv


def empty_storage(x):
    return list(x.list()) == []


def items(s):
    return {x[1].raw for x in s.items.values()}


def test_irrelevant_status():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {"1": ("1", 1234, "1.ics", 2345)}
    sync(a, b, status)
    assert not status
    assert not items(a)
    assert not items(b)


def test_missing_status():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    item = Item("asdf")
    a.upload(item)
    b.upload(item)
    sync(a, b, status)
    assert len(status) == 1
    assert items(a) == items(b) == {item.raw}


def test_missing_status_and_different_items():
    a = MemoryStorage()
    b = MemoryStorage()

    status = {}
    item1 = Item("UID:1\nhaha")
    item2 = Item("UID:1\nhoho")
    a.upload(item1)
    b.upload(item2)
    with pytest.raises(SyncConflict):
        sync(a, b, status)
    assert not status
    sync(a, b, status, conflict_resolution="a wins")
    assert items(a) == items(b) == {item1.raw}


def test_read_only_and_prefetch():
    a = MemoryStorage()
    b = MemoryStorage()
    b.read_only = True

    status = {}
    item1 = Item("UID:1\nhaha")
    item2 = Item("UID:2\nhoho")
    a.upload(item1)
    a.upload(item2)

    sync(a, b, status, force_delete=True)
    sync(a, b, status, force_delete=True)

    assert not items(a) and not items(b)


def test_partial_sync_error():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}

    a.upload(Item("UID:0"))
    b.read_only = True

    with pytest.raises(PartialSync):
        sync(a, b, status, partial_sync="error")


def test_partial_sync_ignore():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}

    item0 = Item("UID:0\nhehe")
    a.upload(item0)
    b.upload(item0)

    b.read_only = True

    item1 = Item("UID:1\nhaha")
    a.upload(item1)

    sync(a, b, status, partial_sync="ignore")
    sync(a, b, status, partial_sync="ignore")

    assert items(a) == {item0.raw, item1.raw}
    assert items(b) == {item0.raw}


def test_partial_sync_ignore2():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}

    href, etag = a.upload(Item("UID:0"))
    a.read_only = True

    sync(a, b, status, partial_sync="ignore", force_delete=True)
    assert items(b) == items(a) == {"UID:0"}

    b.items.clear()
    sync(a, b, status, partial_sync="ignore", force_delete=True)
    sync(a, b, status, partial_sync="ignore", force_delete=True)
    assert items(a) == {"UID:0"}
    assert not b.items

    a.read_only = False
    a.update(href, Item("UID:0\nupdated"), etag)
    a.read_only = True
    sync(a, b, status, partial_sync="ignore", force_delete=True)
    assert items(b) == items(a) == {"UID:0\nupdated"}


def test_upload_and_update():
    a = MemoryStorage(fileext=".a")
    b = MemoryStorage(fileext=".b")
    status = {}

    item = Item("UID:1")  # new item 1 in a
    a.upload(item)
    sync(a, b, status)
    assert items(b) == items(a) == {item.raw}

    item = Item("UID:1\nASDF:YES")  # update of item 1 in b
    b.update("1.b", item, b.get("1.b")[1])
    sync(a, b, status)
    assert items(b) == items(a) == {item.raw}

    item2 = Item("UID:2")  # new item 2 in b
    b.upload(item2)
    sync(a, b, status)
    assert items(b) == items(a) == {item.raw, item2.raw}

    item2 = Item("UID:2\nASDF:YES")  # update of item 2 in a
    a.update("2.a", item2, a.get("2.a")[1])
    sync(a, b, status)
    assert items(b) == items(a) == {item.raw, item2.raw}


def test_deletion():
    a = MemoryStorage(fileext=".a")
    b = MemoryStorage(fileext=".b")
    status = {}

    item = Item("UID:1")
    a.upload(item)
    item2 = Item("UID:2")
    a.upload(item2)
    sync(a, b, status)
    b.delete("1.b", b.get("1.b")[1])
    sync(a, b, status)
    assert items(a) == items(b) == {item2.raw}

    a.upload(item)
    sync(a, b, status)
    assert items(a) == items(b) == {item.raw, item2.raw}
    a.delete("1.a", a.get("1.a")[1])
    sync(a, b, status)
    assert items(a) == items(b) == {item2.raw}


def test_insert_hash():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}

    item = Item("UID:1")
    href, etag = a.upload(item)
    sync(a, b, status)

    for d in status["1"]:
        del d["hash"]

    a.update(href, Item("UID:1\nHAHA:YES"), etag)
    sync(a, b, status)
    assert "hash" in status["1"][0] and "hash" in status["1"][1]


def test_already_synced():
    a = MemoryStorage(fileext=".a")
    b = MemoryStorage(fileext=".b")
    item = Item("UID:1")
    a.upload(item)
    b.upload(item)
    status = {
        "1": (
            {"href": "1.a", "hash": item.hash, "etag": a.get("1.a")[1]},
            {"href": "1.b", "hash": item.hash, "etag": b.get("1.b")[1]},
        )
    }
    old_status = deepcopy(status)
    a.update = b.update = a.upload = b.upload = lambda *a, **kw: pytest.fail(
        "Method shouldn't have been called."
    )

    for _ in (1, 2):
        sync(a, b, status)
        assert status == old_status
        assert items(a) == items(b) == {item.raw}


@pytest.mark.parametrize("winning_storage", "ab")
def test_conflict_resolution_both_etags_new(winning_storage):
    a = MemoryStorage()
    b = MemoryStorage()
    item = Item("UID:1")
    href_a, etag_a = a.upload(item)
    href_b, etag_b = b.upload(item)
    status = {}
    sync(a, b, status)
    assert status
    item_a = Item("UID:1\nitem a")
    item_b = Item("UID:1\nitem b")
    a.update(href_a, item_a, etag_a)
    b.update(href_b, item_b, etag_b)
    with pytest.raises(SyncConflict):
        sync(a, b, status)
    sync(a, b, status, conflict_resolution=f"{winning_storage} wins")
    assert (
        items(a) == items(b) == {item_a.raw if winning_storage == "a" else item_b.raw}
    )


def test_updated_and_deleted():
    a = MemoryStorage()
    b = MemoryStorage()
    href_a, etag_a = a.upload(Item("UID:1"))
    status = {}
    sync(a, b, status, force_delete=True)

    ((href_b, etag_b),) = b.list()
    b.delete(href_b, etag_b)
    updated = Item("UID:1\nupdated")
    a.update(href_a, updated, etag_a)
    sync(a, b, status, force_delete=True)

    assert items(a) == items(b) == {updated.raw}


def test_conflict_resolution_invalid_mode():
    a = MemoryStorage()
    b = MemoryStorage()
    item_a = Item("UID:1\nitem a")
    item_b = Item("UID:1\nitem b")
    a.upload(item_a)
    b.upload(item_b)
    with pytest.raises(ValueError):
        sync(a, b, {}, conflict_resolution="yolo")


def test_conflict_resolution_new_etags_without_changes():
    a = MemoryStorage()
    b = MemoryStorage()
    item = Item("UID:1")
    href_a, etag_a = a.upload(item)
    href_b, etag_b = b.upload(item)
    status = {"1": (href_a, "BOGUS_a", href_b, "BOGUS_b")}

    sync(a, b, status)

    ((ident, (status_a, status_b)),) = status.items()
    assert ident == "1"
    assert status_a["href"] == href_a
    assert status_a["etag"] == etag_a
    assert status_b["href"] == href_b
    assert status_b["etag"] == etag_b


def test_uses_get_multi(monkeypatch):
    def breakdown(*a, **kw):
        raise AssertionError("Expected use of get_multi")

    get_multi_calls = []

    old_get = MemoryStorage.get

    def get_multi(self, hrefs):
        hrefs = list(hrefs)
        get_multi_calls.append(hrefs)
        for href in hrefs:
            item, etag = old_get(self, href)
            yield href, item, etag

    monkeypatch.setattr(MemoryStorage, "get", breakdown)
    monkeypatch.setattr(MemoryStorage, "get_multi", get_multi)

    a = MemoryStorage()
    b = MemoryStorage()
    item = Item("UID:1")
    expected_href, etag = a.upload(item)

    sync(a, b, {})
    assert get_multi_calls == [[expected_href]]


def test_empty_storage_dataloss():
    a = MemoryStorage()
    b = MemoryStorage()
    a.upload(Item("UID:1"))
    a.upload(Item("UID:2"))
    status = {}
    sync(a, b, status)
    with pytest.raises(StorageEmpty):
        sync(MemoryStorage(), b, status)

    with pytest.raises(StorageEmpty):
        sync(a, MemoryStorage(), status)


def test_no_uids():
    a = MemoryStorage()
    b = MemoryStorage()
    a.upload(Item("ASDF"))
    b.upload(Item("FOOBAR"))
    status = {}
    sync(a, b, status)
    assert items(a) == items(b) == {"ASDF", "FOOBAR"}


def test_changed_uids():
    a = MemoryStorage()
    b = MemoryStorage()
    href_a, etag_a = a.upload(Item("UID:A-ONE"))
    href_b, etag_b = b.upload(Item("UID:B-ONE"))
    status = {}
    sync(a, b, status)

    a.update(href_a, Item("UID:A-TWO"), etag_a)
    sync(a, b, status)


def test_both_readonly():
    a = MemoryStorage(read_only=True)
    b = MemoryStorage(read_only=True)
    assert a.read_only
    assert b.read_only
    status = {}
    with pytest.raises(BothReadOnly):
        sync(a, b, status)


def test_partial_sync_revert():
    a = MemoryStorage(instance_name="a")
    b = MemoryStorage(instance_name="b")
    status = {}
    a.upload(Item("UID:1"))
    b.upload(Item("UID:2"))
    b.read_only = True

    sync(a, b, status, partial_sync="revert")
    assert len(status) == 2
    assert items(a) == {"UID:1", "UID:2"}
    assert items(b) == {"UID:2"}

    sync(a, b, status, partial_sync="revert")
    assert len(status) == 1
    assert items(a) == {"UID:2"}
    assert items(b) == {"UID:2"}

    # Check that updates get reverted
    a.items[next(iter(a.items))] = ("foo", Item("UID:2\nupdated"))
    assert items(a) == {"UID:2\nupdated"}
    sync(a, b, status, partial_sync="revert")
    assert len(status) == 1
    assert items(a) == {"UID:2\nupdated"}
    sync(a, b, status, partial_sync="revert")
    assert items(a) == {"UID:2"}

    # Check that deletions get reverted
    a.items.clear()
    sync(a, b, status, partial_sync="revert", force_delete=True)
    sync(a, b, status, partial_sync="revert", force_delete=True)
    assert items(a) == {"UID:2"}


@pytest.mark.parametrize("sync_inbetween", (True, False))
def test_ident_conflict(sync_inbetween):
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    href_a, etag_a = a.upload(Item("UID:aaa"))
    href_b, etag_b = a.upload(Item("UID:bbb"))
    if sync_inbetween:
        sync(a, b, status)

    a.update(href_a, Item("UID:xxx"), etag_a)
    a.update(href_b, Item("UID:xxx"), etag_b)

    with pytest.raises(IdentConflict):
        sync(a, b, status)


def test_moved_href():
    """
    Concrete application: ppl_ stores contact aliases in filenames, which means
    item's hrefs get changed. Vdirsyncer doesn't synchronize this data, but
    also shouldn't do things like deleting and re-uploading to the server.

    .. _ppl: http://ppladdressbook.org/
    """
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    href, etag = a.upload(Item("UID:haha"))
    sync(a, b, status)

    b.items["lol"] = b.items.pop("haha")

    # The sync algorithm should prefetch `lol`, see that it's the same ident
    # and not do anything else.
    a.get_multi = blow_up  # Absolutely no prefetch on A
    # No actual sync actions
    a.delete = a.update = a.upload = b.delete = b.update = b.upload = blow_up

    sync(a, b, status)
    assert len(status) == 1
    assert items(a) == items(b) == {"UID:haha"}
    assert status["haha"][1]["href"] == "lol"
    old_status = deepcopy(status)

    # Further sync should be a noop. Not even prefetching should occur.
    b.get_multi = blow_up

    sync(a, b, status)
    assert old_status == status
    assert items(a) == items(b) == {"UID:haha"}


def test_bogus_etag_change():
    """Assert that sync algorithm is resilient against etag changes if content
    didn\'t change.

    In this particular case we test a scenario where both etags have been
    updated, but only one side actually changed its item content.
    """
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    href_a, etag_a = a.upload(Item("UID:ASDASD"))
    sync(a, b, status)
    assert len(status) == len(list(a.list())) == len(list(b.list())) == 1

    ((href_b, etag_b),) = b.list()
    a.update(href_a, Item("UID:ASDASD"), etag_a)
    b.update(href_b, Item("UID:ASDASD\nACTUALCHANGE:YES"), etag_b)

    b.delete = b.update = b.upload = blow_up

    sync(a, b, status)
    assert len(status) == 1
    assert items(a) == items(b) == {"UID:ASDASD\nACTUALCHANGE:YES"}


def test_unicode_hrefs():
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}
    href, etag = a.upload(Item("UID:äää"))
    sync(a, b, status)


class ActionIntentionallyFailed(Exception):
    pass


def action_failure(*a, **kw):
    raise ActionIntentionallyFailed()


class SyncMachine(RuleBasedStateMachine):
    Status = Bundle("status")
    Storage = Bundle("storage")

    @rule(target=Storage, flaky_etags=st.booleans(), null_etag_on_upload=st.booleans())
    def newstorage(self, flaky_etags, null_etag_on_upload):
        s = MemoryStorage()
        if flaky_etags:

            def get(href):
                old_etag, item = s.items[href]
                etag = _random_string()
                s.items[href] = etag, item
                return item, etag

            s.get = get

        if null_etag_on_upload:
            _old_upload = s.upload
            _old_update = s.update
            s.upload = lambda item: (_old_upload(item)[0], "NULL")
            s.update = lambda h, i, e: _old_update(h, i, e) and "NULL"

        return s

    @rule(s=Storage, read_only=st.booleans())
    def is_read_only(self, s, read_only):
        assume(s.read_only != read_only)
        s.read_only = read_only

    @rule(s=Storage)
    def actions_fail(self, s):
        s.upload = action_failure
        s.update = action_failure
        s.delete = action_failure

    @rule(s=Storage)
    def none_as_etag(self, s):
        _old_upload = s.upload
        _old_update = s.update

        def upload(item):
            return _old_upload(item)[0], None

        def update(href, item, etag):
            _old_update(href, item, etag)

        s.upload = upload
        s.update = update

    @rule(target=Status)
    def newstatus(self):
        return {}

    @rule(storage=Storage, uid=uid_strategy, etag=st.text())
    def upload(self, storage, uid, etag):
        item = Item(f"UID:{uid}")
        storage.items[uid] = (etag, item)

    @rule(storage=Storage, href=st.text())
    def delete(self, storage, href):
        assume(storage.items.pop(href, None))

    @rule(
        status=Status,
        a=Storage,
        b=Storage,
        force_delete=st.booleans(),
        conflict_resolution=st.one_of((st.just("a wins"), st.just("b wins"))),
        with_error_callback=st.booleans(),
        partial_sync=st.one_of(
            (st.just("ignore"), st.just("revert"), st.just("error"))
        ),
    )
    def sync(
        self,
        status,
        a,
        b,
        force_delete,
        conflict_resolution,
        with_error_callback,
        partial_sync,
    ):
        assume(a is not b)
        old_items_a = items(a)
        old_items_b = items(b)

        a.instance_name = "a"
        b.instance_name = "b"

        errors = []

        if with_error_callback:
            error_callback = errors.append
        else:
            error_callback = None

        try:
            # If one storage is read-only, double-sync because changes don't
            # get reverted immediately.
            for _ in range(2 if a.read_only or b.read_only else 1):
                sync(
                    a,
                    b,
                    status,
                    force_delete=force_delete,
                    conflict_resolution=conflict_resolution,
                    error_callback=error_callback,
                    partial_sync=partial_sync,
                )

            for e in errors:
                raise e
        except PartialSync:
            assert partial_sync == "error"
        except ActionIntentionallyFailed:
            pass
        except BothReadOnly:
            assert a.read_only and b.read_only
            assume(False)
        except StorageEmpty:
            if force_delete:
                raise
            else:
                assert not list(a.list()) or not list(b.list())
        else:
            items_a = items(a)
            items_b = items(b)

            assert items_a == items_b or partial_sync == "ignore"
            assert items_a == old_items_a or not a.read_only
            assert items_b == old_items_b or not b.read_only

            assert (
                set(a.items) | set(b.items) == set(status) or partial_sync == "ignore"
            )


TestSyncMachine = SyncMachine.TestCase


@pytest.mark.parametrize("error_callback", [True, False])
def test_rollback(error_callback):
    a = MemoryStorage()
    b = MemoryStorage()
    status = {}

    a.items["0"] = ("", Item("UID:0"))
    b.items["1"] = ("", Item("UID:1"))

    b.upload = b.update = b.delete = action_failure

    if error_callback:
        errors = []

        sync(
            a,
            b,
            status=status,
            conflict_resolution="a wins",
            error_callback=errors.append,
        )

        assert len(errors) == 1
        assert isinstance(errors[0], ActionIntentionallyFailed)

        assert len(status) == 1
        assert status["1"]
    else:
        with pytest.raises(ActionIntentionallyFailed):
            sync(a, b, status=status, conflict_resolution="a wins")


def test_duplicate_hrefs():
    a = MemoryStorage()
    b = MemoryStorage()
    a.list = lambda: [("a", "a")] * 3
    a.items["a"] = ("a", Item("UID:a"))

    status = {}
    sync(a, b, status)
    with pytest.raises(AssertionError):
        sync(a, b, status)
