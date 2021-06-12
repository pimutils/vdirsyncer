import random
import textwrap
import uuid
from urllib.parse import quote as urlquote
from urllib.parse import unquote as urlunquote

import pytest

from .. import assert_item_equals
from .. import EVENT_TEMPLATE
from .. import normalize_item
from .. import TASK_TEMPLATE
from .. import VCARD_TEMPLATE
from vdirsyncer import exceptions
from vdirsyncer.storage.base import normalize_meta_value
from vdirsyncer.vobject import Item


def get_server_mixin(server_name):
    from . import __name__ as base

    x = __import__(f"{base}.servers.{server_name}", fromlist=[""])
    return x.ServerMixin


def format_item(item_template, uid=None):
    # assert that special chars are handled correctly.
    r = random.random()
    return Item(item_template.format(r=r, uid=uid or r))


class StorageTests:
    storage_class = None
    supports_collections = True
    supports_metadata = True

    @pytest.fixture(params=["VEVENT", "VTODO", "VCARD"])
    def item_type(self, request):
        """Parametrize with all supported item types."""
        return request.param

    @pytest.fixture
    def get_storage_args(self):
        """
        Return a function with the following properties:

        :param collection: The name of the collection to create and use.
        """
        raise NotImplementedError()

    @pytest.fixture
    def s(self, get_storage_args):
        return self.storage_class(**get_storage_args())

    @pytest.fixture
    def get_item(self, item_type):
        template = {
            "VEVENT": EVENT_TEMPLATE,
            "VTODO": TASK_TEMPLATE,
            "VCARD": VCARD_TEMPLATE,
        }[item_type]

        return lambda **kw: format_item(template, **kw)

    @pytest.fixture
    def requires_collections(self):
        if not self.supports_collections:
            pytest.skip("This storage does not support collections.")

    @pytest.fixture
    def requires_metadata(self):
        if not self.supports_metadata:
            pytest.skip("This storage does not support metadata.")

    def test_generic(self, s, get_item):
        items = [get_item() for i in range(1, 10)]
        hrefs = []
        for item in items:
            href, etag = s.upload(item)
            if etag is None:
                _, etag = s.get(href)
            hrefs.append((href, etag))
        hrefs.sort()
        assert hrefs == sorted(s.list())
        for href, etag in hrefs:
            assert isinstance(href, (str, bytes))
            assert isinstance(etag, (str, bytes))
            assert s.has(href)
            item, etag2 = s.get(href)
            assert etag == etag2

    def test_empty_get_multi(self, s):
        assert list(s.get_multi([])) == []

    def test_get_multi_duplicates(self, s, get_item):
        href, etag = s.upload(get_item())
        if etag is None:
            _, etag = s.get(href)
        ((href2, item, etag2),) = s.get_multi([href] * 2)
        assert href2 == href
        assert etag2 == etag

    def test_upload_already_existing(self, s, get_item):
        item = get_item()
        s.upload(item)
        with pytest.raises(exceptions.PreconditionFailed):
            s.upload(item)

    def test_upload(self, s, get_item):
        item = get_item()
        href, etag = s.upload(item)
        assert_item_equals(s.get(href)[0], item)

    def test_update(self, s, get_item):
        item = get_item()
        href, etag = s.upload(item)
        if etag is None:
            _, etag = s.get(href)
        assert_item_equals(s.get(href)[0], item)

        new_item = get_item(uid=item.uid)
        new_etag = s.update(href, new_item, etag)
        if new_etag is None:
            _, new_etag = s.get(href)
        # See https://github.com/pimutils/vdirsyncer/issues/48
        assert isinstance(new_etag, (bytes, str))
        assert_item_equals(s.get(href)[0], new_item)

    def test_update_nonexisting(self, s, get_item):
        item = get_item()
        with pytest.raises(exceptions.PreconditionFailed):
            s.update("huehue", item, '"123"')

    def test_wrong_etag(self, s, get_item):
        item = get_item()
        href, etag = s.upload(item)
        with pytest.raises(exceptions.PreconditionFailed):
            s.update(href, item, '"lolnope"')
        with pytest.raises(exceptions.PreconditionFailed):
            s.delete(href, '"lolnope"')

    def test_delete(self, s, get_item):
        href, etag = s.upload(get_item())
        s.delete(href, etag)
        assert not list(s.list())

    def test_delete_nonexisting(self, s, get_item):
        with pytest.raises(exceptions.PreconditionFailed):
            s.delete("1", '"123"')

    def test_list(self, s, get_item):
        assert not list(s.list())
        href, etag = s.upload(get_item())
        if etag is None:
            _, etag = s.get(href)
        assert list(s.list()) == [(href, etag)]

    def test_has(self, s, get_item):
        assert not s.has("asd")
        href, etag = s.upload(get_item())
        assert s.has(href)
        assert not s.has("asd")
        s.delete(href, etag)
        assert not s.has(href)

    def test_update_others_stay_the_same(self, s, get_item):
        info = {}
        for _ in range(4):
            href, etag = s.upload(get_item())
            if etag is None:
                _, etag = s.get(href)
            info[href] = etag

        assert {
            href: etag
            for href, item, etag in s.get_multi(href for href, etag in info.items())
        } == info

    def test_repr(self, s, get_storage_args):
        assert self.storage_class.__name__ in repr(s)
        assert s.instance_name is None

    def test_discover(self, requires_collections, get_storage_args, get_item):
        collections = set()
        for i in range(1, 5):
            collection = f"test{i}"
            s = self.storage_class(**get_storage_args(collection=collection))
            assert not list(s.list())
            s.upload(get_item())
            collections.add(s.collection)

        actual = {
            c["collection"]
            for c in self.storage_class.discover(**get_storage_args(collection=None))
        }

        assert actual >= collections

    def test_create_collection(self, requires_collections, get_storage_args, get_item):
        if getattr(self, "dav_server", "") in ("icloud", "fastmail", "davical"):
            pytest.skip("Manual cleanup would be necessary.")
        if getattr(self, "dav_server", "") == "radicale":
            pytest.skip("Radicale does not support collection creation")

        args = get_storage_args(collection=None)
        args["collection"] = "test"

        s = self.storage_class(**self.storage_class.create_collection(**args))

        href = s.upload(get_item())[0]
        assert href in (href for href, etag in s.list())

    def test_discover_collection_arg(self, requires_collections, get_storage_args):
        args = get_storage_args(collection="test2")
        with pytest.raises(TypeError) as excinfo:
            list(self.storage_class.discover(**args))

        assert "collection argument must not be given" in str(excinfo.value)

    def test_collection_arg(self, get_storage_args):
        if self.storage_class.storage_name.startswith("etesync"):
            pytest.skip("etesync uses UUIDs.")

        if self.supports_collections:
            s = self.storage_class(**get_storage_args(collection="test2"))
            # Can't do stronger assertion because of radicale, which needs a
            # fileextension to guess the collection type.
            assert "test2" in s.collection
        else:
            with pytest.raises(ValueError):
                self.storage_class(collection="ayy", **get_storage_args())

    def test_case_sensitive_uids(self, s, get_item):
        if s.storage_name == "filesystem":
            pytest.skip("Behavior depends on the filesystem.")

        uid = str(uuid.uuid4())
        s.upload(get_item(uid=uid.upper()))
        s.upload(get_item(uid=uid.lower()))
        items = [href for href, etag in s.list()]
        assert len(items) == 2
        assert len(set(items)) == 2

    def test_specialchars(
        self, monkeypatch, requires_collections, get_storage_args, get_item
    ):
        if getattr(self, "dav_server", "") == "radicale":
            pytest.skip("Radicale is fundamentally broken.")
        if getattr(self, "dav_server", "") in ("icloud", "fastmail"):
            pytest.skip("iCloud and FastMail reject this name.")

        monkeypatch.setattr("vdirsyncer.utils.generate_href", lambda x: x)

        uid = "test @ foo ät bar град сатану"
        collection = "test @ foo ät bar"

        s = self.storage_class(**get_storage_args(collection=collection))
        item = get_item(uid=uid)

        href, etag = s.upload(item)
        item2, etag2 = s.get(href)
        if etag is not None:
            assert etag2 == etag
            assert_item_equals(item2, item)

        ((_, etag3),) = s.list()
        assert etag2 == etag3

        # etesync uses UUIDs for collection names
        if self.storage_class.storage_name.startswith("etesync"):
            return

        assert collection in urlunquote(s.collection)
        if self.storage_class.storage_name.endswith("dav"):
            assert urlquote(uid, "/@:") in href

    def test_metadata(self, requires_metadata, s):
        if not getattr(self, "dav_server", ""):
            assert not s.get_meta("color")
            assert not s.get_meta("displayname")

        try:
            s.set_meta("color", None)
            assert not s.get_meta("color")
            s.set_meta("color", "#ff0000")
            assert s.get_meta("color") == "#ff0000"
        except exceptions.UnsupportedMetadataError:
            pass

        for x in ("hello world", "hello wörld"):
            s.set_meta("displayname", x)
            rv = s.get_meta("displayname")
            assert rv == x
            assert isinstance(rv, str)

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "Hello there!",
            "Österreich",
            "中国",
            "한글",
            "42a4ec99-b1c2-4859-b142-759112f2ca50",
            "فلسطين",
        ],
    )
    def test_metadata_normalization(self, requires_metadata, s, value):
        x = s.get_meta("displayname")
        assert x == normalize_meta_value(x)

        if not getattr(self, "dav_server", None):
            # ownCloud replaces "" with "unnamed"
            s.set_meta("displayname", value)
            assert s.get_meta("displayname") == normalize_meta_value(value)

    def test_recurring_events(self, s, item_type):
        if item_type != "VEVENT":
            pytest.skip("This storage instance doesn't support iCalendar.")

        uid = str(uuid.uuid4())
        item = Item(
            textwrap.dedent(
                """
        BEGIN:VCALENDAR
        VERSION:2.0
        BEGIN:VEVENT
        DTSTART;TZID=UTC:20140325T084000Z
        DTEND;TZID=UTC:20140325T101000Z
        DTSTAMP:20140327T060506Z
        UID:{uid}
        RECURRENCE-ID;TZID=UTC:20140325T083000Z
        CREATED:20131216T033331Z
        DESCRIPTION:
        LAST-MODIFIED:20140327T060215Z
        LOCATION:
        SEQUENCE:1
        STATUS:CONFIRMED
        SUMMARY:test Event
        TRANSP:OPAQUE
        END:VEVENT
        BEGIN:VEVENT
        DTSTART;TZID=UTC:20140128T083000Z
        DTEND;TZID=UTC:20140128T100000Z
        RRULE:FREQ=WEEKLY;UNTIL=20141208T213000Z;BYDAY=TU
        DTSTAMP:20140327T060506Z
        UID:{uid}
        CREATED:20131216T033331Z
        DESCRIPTION:
        LAST-MODIFIED:20140222T101012Z
        LOCATION:
        SEQUENCE:0
        STATUS:CONFIRMED
        SUMMARY:Test event
        TRANSP:OPAQUE
        END:VEVENT
        END:VCALENDAR
        """.format(
                    uid=uid
                )
            ).strip()
        )

        href, etag = s.upload(item)

        item2, etag2 = s.get(href)
        assert normalize_item(item) == normalize_item(item2)
