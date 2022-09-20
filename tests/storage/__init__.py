import random
import textwrap
import uuid
from urllib.parse import quote as urlquote
from urllib.parse import unquote as urlunquote

import aiostream
import pytest
import pytest_asyncio

from vdirsyncer import exceptions
from vdirsyncer.storage.base import normalize_meta_value
from vdirsyncer.vobject import Item

from .. import EVENT_TEMPLATE
from .. import TASK_TEMPLATE
from .. import VCARD_TEMPLATE
from .. import assert_item_equals
from .. import normalize_item


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

    @pytest_asyncio.fixture
    async def s(self, get_storage_args):
        rv = self.storage_class(**await get_storage_args())
        return rv

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

    @pytest.mark.asyncio
    async def test_generic(self, s, get_item):
        items = [get_item() for i in range(1, 10)]
        hrefs = []
        for item in items:
            href, etag = await s.upload(item)
            if etag is None:
                _, etag = await s.get(href)
            hrefs.append((href, etag))
        hrefs.sort()
        assert hrefs == sorted(await aiostream.stream.list(s.list()))
        for href, etag in hrefs:
            assert isinstance(href, (str, bytes))
            assert isinstance(etag, (str, bytes))
            assert await s.has(href)
            item, etag2 = await s.get(href)
            assert etag == etag2

    @pytest.mark.asyncio
    async def test_empty_get_multi(self, s):
        assert await aiostream.stream.list(s.get_multi([])) == []

    @pytest.mark.asyncio
    async def test_get_multi_duplicates(self, s, get_item):
        href, etag = await s.upload(get_item())
        if etag is None:
            _, etag = await s.get(href)
        ((href2, item, etag2),) = await aiostream.stream.list(s.get_multi([href] * 2))
        assert href2 == href
        assert etag2 == etag

    @pytest.mark.asyncio
    async def test_upload_already_existing(self, s, get_item):
        item = get_item()
        await s.upload(item)
        with pytest.raises(exceptions.PreconditionFailed):
            await s.upload(item)

    @pytest.mark.asyncio
    async def test_upload(self, s, get_item):
        item = get_item()
        href, etag = await s.upload(item)
        assert_item_equals((await s.get(href))[0], item)

    @pytest.mark.asyncio
    async def test_update(self, s, get_item):
        item = get_item()
        href, etag = await s.upload(item)
        if etag is None:
            _, etag = await s.get(href)
        assert_item_equals((await s.get(href))[0], item)

        new_item = get_item(uid=item.uid)
        new_etag = await s.update(href, new_item, etag)
        if new_etag is None:
            _, new_etag = await s.get(href)
        # See https://github.com/pimutils/vdirsyncer/issues/48
        assert isinstance(new_etag, (bytes, str))
        assert_item_equals((await s.get(href))[0], new_item)

    @pytest.mark.asyncio
    async def test_update_nonexisting(self, s, get_item):
        item = get_item()
        with pytest.raises(exceptions.PreconditionFailed):
            await s.update("huehue", item, '"123"')

    @pytest.mark.asyncio
    async def test_wrong_etag(self, s, get_item):
        item = get_item()
        href, etag = await s.upload(item)
        with pytest.raises(exceptions.PreconditionFailed):
            await s.update(href, item, '"lolnope"')
        with pytest.raises(exceptions.PreconditionFailed):
            await s.delete(href, '"lolnope"')

    @pytest.mark.asyncio
    async def test_delete(self, s, get_item):
        href, etag = await s.upload(get_item())
        await s.delete(href, etag)
        assert not await aiostream.stream.list(s.list())

    @pytest.mark.asyncio
    async def test_delete_nonexisting(self, s, get_item):
        with pytest.raises(exceptions.PreconditionFailed):
            await s.delete("1", '"123"')

    @pytest.mark.asyncio
    async def test_list(self, s, get_item):
        assert not await aiostream.stream.list(s.list())
        href, etag = await s.upload(get_item())
        if etag is None:
            _, etag = await s.get(href)
        assert await aiostream.stream.list(s.list()) == [(href, etag)]

    @pytest.mark.asyncio
    async def test_has(self, s, get_item):
        assert not await s.has("asd")
        href, etag = await s.upload(get_item())
        assert await s.has(href)
        assert not await s.has("asd")
        await s.delete(href, etag)
        assert not await s.has(href)

    @pytest.mark.asyncio
    async def test_update_others_stay_the_same(self, s, get_item):
        info = {}
        for _ in range(4):
            href, etag = await s.upload(get_item())
            if etag is None:
                _, etag = await s.get(href)
            info[href] = etag

        items = await aiostream.stream.list(
            s.get_multi(href for href, etag in info.items())
        )
        assert {href: etag for href, item, etag in items} == info

    @pytest.mark.asyncio
    def test_repr(self, s, get_storage_args):  # XXX: unused param
        assert self.storage_class.__name__ in repr(s)
        assert s.instance_name is None

    @pytest.mark.asyncio
    async def test_discover(
        self,
        requires_collections,
        get_storage_args,
        get_item,
        aio_connector,
    ):
        collections = set()
        for i in range(1, 5):
            collection = f"test{i}"
            s = self.storage_class(**await get_storage_args(collection=collection))
            assert not await aiostream.stream.list(s.list())
            await s.upload(get_item())
            collections.add(s.collection)

        discovered = await aiostream.stream.list(
            self.storage_class.discover(**await get_storage_args(collection=None))
        )
        actual = {c["collection"] for c in discovered}

        assert actual >= collections

    @pytest.mark.asyncio
    async def test_create_collection(
        self,
        requires_collections,
        get_storage_args,
        get_item,
    ):
        if getattr(self, "dav_server", "") in ("icloud", "fastmail", "davical"):
            pytest.skip("Manual cleanup would be necessary.")
        if getattr(self, "dav_server", "") == "radicale":
            pytest.skip("Radicale does not support collection creation")

        args = await get_storage_args(collection=None)
        args["collection"] = "test"

        s = self.storage_class(**await self.storage_class.create_collection(**args))

        href = (await s.upload(get_item()))[0]
        assert href in await aiostream.stream.list(
            (href async for href, etag in s.list())
        )

    @pytest.mark.asyncio
    async def test_discover_collection_arg(
        self, requires_collections, get_storage_args
    ):
        args = await get_storage_args(collection="test2")
        with pytest.raises(TypeError) as excinfo:
            await aiostream.stream.list(self.storage_class.discover(**args))

        assert "collection argument must not be given" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_collection_arg(self, get_storage_args):
        if self.supports_collections:
            s = self.storage_class(**await get_storage_args(collection="test2"))
            # Can't do stronger assertion because of radicale, which needs a
            # fileextension to guess the collection type.
            assert "test2" in s.collection
        else:
            with pytest.raises(ValueError):
                self.storage_class(collection="ayy", **await get_storage_args())

    @pytest.mark.asyncio
    async def test_case_sensitive_uids(self, s, get_item):
        if s.storage_name == "filesystem":
            pytest.skip("Behavior depends on the filesystem.")

        uid = str(uuid.uuid4())
        await s.upload(get_item(uid=uid.upper()))
        await s.upload(get_item(uid=uid.lower()))
        items = [href async for href, etag in s.list()]
        assert len(items) == 2
        assert len(set(items)) == 2

    @pytest.mark.asyncio
    async def test_specialchars(
        self, monkeypatch, requires_collections, get_storage_args, get_item
    ):
        if getattr(self, "dav_server", "") in ("icloud", "fastmail"):
            pytest.skip("iCloud and FastMail reject this name.")

        monkeypatch.setattr("vdirsyncer.utils.generate_href", lambda x: x)

        uid = "test @ foo ät bar град сатану"
        collection = "test @ foo ät bar"

        s = self.storage_class(**await get_storage_args(collection=collection))
        item = get_item(uid=uid)

        href, etag = await s.upload(item)
        item2, etag2 = await s.get(href)
        if etag is not None:
            assert etag2 == etag
            assert_item_equals(item2, item)

        ((_, etag3),) = await aiostream.stream.list(s.list())
        assert etag2 == etag3

        assert collection in urlunquote(s.collection)
        if self.storage_class.storage_name.endswith("dav"):
            assert urlquote(uid, "/@:") in href

    @pytest.mark.asyncio
    async def test_newline_in_uid(
        self, monkeypatch, requires_collections, get_storage_args, get_item
    ):
        monkeypatch.setattr("vdirsyncer.utils.generate_href", lambda x: x)

        uid = "UID:20210609T084907Z-@synaps-web-54fddfdf7-7kcfm%0A.ics"

        s = self.storage_class(**await get_storage_args())
        item = get_item(uid=uid)

        href, etag = await s.upload(item)
        item2, etag2 = await s.get(href)
        if etag is not None:
            assert etag2 == etag
            assert_item_equals(item2, item)

        ((_, etag3),) = await aiostream.stream.list(s.list())
        assert etag2 == etag3

    @pytest.mark.asyncio
    async def test_empty_metadata(self, requires_metadata, s):
        if getattr(self, "dav_server", ""):
            pytest.skip()

        assert await s.get_meta("color") is None
        assert await s.get_meta("displayname") is None

    @pytest.mark.asyncio
    async def test_metadata(self, requires_metadata, s):
        if getattr(self, "dav_server", "") == "xandikos":
            pytest.skip("xandikos does not support removing metadata.")

        try:
            await s.set_meta("color", None)
            assert await s.get_meta("color") is None
            await s.set_meta("color", "#ff0000")
            assert await s.get_meta("color") == "#ff0000"
        except exceptions.UnsupportedMetadataError:
            pass

    @pytest.mark.asyncio
    async def test_encoding_metadata(self, requires_metadata, s):
        for x in ("hello world", "hello wörld"):
            await s.set_meta("displayname", x)
            rv = await s.get_meta("displayname")
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
    @pytest.mark.asyncio
    async def test_metadata_normalization(self, requires_metadata, s, value):
        x = await s.get_meta("displayname")
        assert x == normalize_meta_value(x)

        if not getattr(self, "dav_server", None):
            # ownCloud replaces "" with "unnamed"
            await s.set_meta("displayname", value)
            assert await s.get_meta("displayname") == normalize_meta_value(value)

    @pytest.mark.asyncio
    async def test_recurring_events(self, s, item_type):
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
        RRULE:FREQ=WEEKLY;BYDAY=TU;UNTIL=20141208T213000Z
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

        href, etag = await s.upload(item)

        item2, etag2 = await s.get(href)
        assert normalize_item(item) == normalize_item(item2)
