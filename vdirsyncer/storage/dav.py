import datetime
import logging
import urllib.parse as urlparse
import xml.etree.ElementTree as etree
from abc import abstractmethod
from inspect import getfullargspec
from inspect import signature
from typing import Optional
from typing import Type

import aiohttp
import aiostream

from vdirsyncer.exceptions import Error
from vdirsyncer.vobject import Item

from .. import exceptions
from .. import http
from .. import utils
from ..http import USERAGENT
from ..http import prepare_auth
from ..http import prepare_client_cert
from ..http import prepare_verify
from .base import Storage
from .base import normalize_meta_value

dav_logger = logging.getLogger(__name__)

CALDAV_DT_FORMAT = "%Y%m%dT%H%M%SZ"


async def _assert_multistatus_success(r):
    # Xandikos returns a multistatus on PUT.
    try:
        root = _parse_xml(await r.content.read())
    except InvalidXMLResponse:
        return
    for status in root.findall(".//{DAV:}status"):
        parts = status.text.strip().split()
        try:
            st = int(parts[1])
        except (ValueError, IndexError):
            continue
        if st < 200 or st >= 400:
            raise Error(f"Server error: {st}")


def _normalize_href(base, href):
    """Normalize the href to be a path only relative to hostname and schema."""
    orig_href = href
    if not href:
        raise ValueError(href)

    x = urlparse.urljoin(base, href)
    x = urlparse.urlsplit(x).path

    # We unquote and quote again, but want to make sure we
    # keep around the "@" character.
    x = urlparse.unquote(x)
    x = urlparse.quote(x, "/@")

    if orig_href == x:
        dav_logger.debug(f"Already normalized: {x!r}")
    else:
        dav_logger.debug(f"Normalized URL from {orig_href!r} to {x!r}")

    return x


class InvalidXMLResponse(exceptions.InvalidResponse):
    pass


_BAD_XML_CHARS = (
    b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"
    b"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
)


def _clean_body(content, bad_chars=_BAD_XML_CHARS):
    new_content = content.translate(None, bad_chars)
    if new_content != content:
        dav_logger.warning(
            "Your server incorrectly returned ASCII control characters in its "
            "XML. Vdirsyncer ignores those, but this is a bug in your server."
        )
    return new_content


def _parse_xml(content):
    try:
        return etree.XML(_clean_body(content))
    except etree.ParseError as e:
        raise InvalidXMLResponse(
            "Invalid XML encountered: {}\n"
            "Double-check the URLs in your config.".format(e)
        )


def _merge_xml(items):
    if not items:
        return None
    rv = items[0]
    for item in items[1:]:
        rv.extend(item.iter())
    return rv


def _fuzzy_matches_mimetype(strict, weak):
    # different servers give different getcontenttypes:
    # "text/vcard", "text/x-vcard", "text/x-vcard; charset=utf-8",
    # "text/directory;profile=vCard", "text/directory",
    # "text/vcard; charset=utf-8"
    if strict is None or weak is None:
        return True

    mediatype, subtype = strict.split("/")
    if subtype in weak:
        return True
    return False


class Discover:
    @property
    @abstractmethod
    def _namespace(self) -> str:
        pass

    @property
    @abstractmethod
    def _resourcetype(self) -> Optional[str]:
        pass

    @property
    @abstractmethod
    def _homeset_xml(self) -> bytes:
        pass

    @property
    @abstractmethod
    def _homeset_tag(self) -> str:
        pass

    @property
    @abstractmethod
    def _well_known_uri(self) -> str:
        pass

    _collection_xml = b"""
    <propfind xmlns="DAV:">
        <prop>
            <resourcetype />
        </prop>
    </propfind>
    """

    def __init__(self, session, kwargs):
        if kwargs.pop("collection", None) is not None:
            raise TypeError("collection argument must not be given.")

        self.session = session
        self.kwargs = kwargs

    @staticmethod
    def _get_collection_from_url(url):
        _, collection = url.rstrip("/").rsplit("/", 1)
        return urlparse.unquote(collection)

    async def find_principal(self):
        try:
            return await self._find_principal_impl("")
        except (aiohttp.ClientResponseError, exceptions.Error):
            dav_logger.debug("Trying out well-known URI")
            return await self._find_principal_impl(self._well_known_uri)

    async def _find_principal_impl(self, url):
        headers = self.session.get_default_headers()
        headers["Depth"] = "0"
        body = b"""
        <propfind xmlns="DAV:">
            <prop>
                <current-user-principal />
            </prop>
        </propfind>
        """

        response = await self.session.request(
            "PROPFIND",
            url,
            headers=headers,
            data=body,
        )

        root = _parse_xml(await response.content.read())
        rv = root.find(".//{DAV:}current-user-principal/{DAV:}href")
        if rv is None:
            # This is for servers that don't support current-user-principal
            # E.g. Synology NAS
            # See https://github.com/pimutils/vdirsyncer/issues/498
            dav_logger.debug(
                "No current-user-principal returned, re-using URL {}".format(
                    response.url
                )
            )
            return response.url
        return urlparse.urljoin(str(response.url), rv.text).rstrip("/") + "/"

    async def find_home(self):
        url = await self.find_principal()
        headers = self.session.get_default_headers()
        headers["Depth"] = "0"
        response = await self.session.request(
            "PROPFIND", url, headers=headers, data=self._homeset_xml
        )

        root = etree.fromstring(await response.content.read())
        # Better don't do string formatting here, because of XML namespaces
        rv = root.find(".//" + self._homeset_tag + "/{DAV:}href")
        if rv is None:
            raise InvalidXMLResponse("Couldn't find home-set.")
        return urlparse.urljoin(str(response.url), rv.text).rstrip("/") + "/"

    async def find_collections(self):
        rv = None
        try:
            rv = await aiostream.stream.list(self._find_collections_impl(""))
        except (aiohttp.ClientResponseError, exceptions.Error):
            pass

        if rv:
            return rv

        dav_logger.debug("Given URL is not a homeset URL")
        return await aiostream.stream.list(
            self._find_collections_impl(await self.find_home())
        )

    def _check_collection_resource_type(self, response):
        if self._resourcetype is None:
            return True

        props = _merge_xml(response.findall("{DAV:}propstat/{DAV:}prop"))
        if props is None or not len(props):
            dav_logger.debug("Skipping, missing <prop>: %s", response)
            return False
        if props.find("{DAV:}resourcetype/" + self._resourcetype) is None:
            dav_logger.debug(
                "Skipping, not of resource type %s: %s", self._resourcetype, response
            )
            return False
        return True

    async def _find_collections_impl(self, url):
        headers = self.session.get_default_headers()
        headers["Depth"] = "1"
        r = await self.session.request(
            "PROPFIND", url, headers=headers, data=self._collection_xml
        )
        root = _parse_xml(await r.content.read())
        done = set()
        for response in root.findall("{DAV:}response"):
            if not self._check_collection_resource_type(response):
                continue

            href = response.find("{DAV:}href")
            if href is None:
                raise InvalidXMLResponse("Missing href tag for collection " "props.")
            href = urlparse.urljoin(str(r.url), href.text)
            if href not in done:
                done.add(href)
                yield {"href": href}

    async def discover(self):
        for c in await self.find_collections():
            url = c["href"]
            collection = self._get_collection_from_url(url)
            storage_args = dict(self.kwargs)
            storage_args.update({"url": url, "collection": collection})
            yield storage_args

    async def create(self, collection):
        if collection is None:
            collection = self._get_collection_from_url(self.kwargs["url"])

        async for c in self.discover():
            if c["collection"] == collection:
                return c

        home = await self.find_home()
        url = urlparse.urljoin(home, urlparse.quote(collection, "/@"))

        try:
            url = await self._create_collection_impl(url)
        except (aiohttp.ClientResponseError, Error) as e:
            raise NotImplementedError(e)
        else:
            rv = dict(self.kwargs)
            rv["collection"] = collection
            rv["url"] = url
            return rv

    async def _create_collection_impl(self, url):
        data = """<?xml version="1.0" encoding="utf-8" ?>
            <mkcol xmlns="DAV:">
                <set>
                    <prop>
                        <resourcetype>
                            <collection/>
                            {}
                        </resourcetype>
                    </prop>
                </set>
            </mkcol>
        """.format(
            etree.tostring(etree.Element(self._resourcetype), encoding="unicode")
        ).encode(
            "utf-8"
        )

        response = await self.session.request(
            "MKCOL",
            url,
            data=data,
            headers=self.session.get_default_headers(),
        )
        return str(response.url)


class CalDiscover(Discover):
    _namespace = "urn:ietf:params:xml:ns:caldav"
    _resourcetype = "{%s}calendar" % _namespace
    _homeset_xml = b"""
    <propfind xmlns="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
        <prop>
            <c:calendar-home-set />
        </prop>
    </propfind>
    """
    _homeset_tag = "{%s}calendar-home-set" % _namespace
    _well_known_uri = "/.well-known/caldav"


class CardDiscover(Discover):
    _namespace = "urn:ietf:params:xml:ns:carddav"
    _resourcetype: Optional[str] = "{%s}addressbook" % _namespace
    _homeset_xml = b"""
    <propfind xmlns="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">
        <prop>
            <c:addressbook-home-set />
        </prop>
    </propfind>
    """
    _homeset_tag = "{%s}addressbook-home-set" % _namespace
    _well_known_uri = "/.well-known/carddav"


class DAVSession:
    """A helper class to connect to DAV servers."""

    connector: aiohttp.BaseConnector

    @classmethod
    def init_and_remaining_args(cls, **kwargs):
        def is_arg(k):
            """Return true if ``k`` is an argument of ``cls.__init__``."""
            return k in argspec.args or k in argspec.kwonlyargs

        argspec = getfullargspec(cls.__init__)
        self_args, remainder = utils.split_dict(kwargs, is_arg)

        return cls(**self_args), remainder

    def __init__(
        self,
        url,
        username="",
        password="",
        verify=None,
        auth=None,
        useragent=USERAGENT,
        verify_fingerprint=None,
        auth_cert=None,
        *,
        connector: aiohttp.BaseConnector,
    ):
        self._settings = {
            "cert": prepare_client_cert(auth_cert),
        }
        auth = prepare_auth(auth, username, password)
        if auth:
            self._settings["auth"] = auth

        ssl = prepare_verify(verify, verify_fingerprint)
        if ssl:
            self._settings["ssl"] = ssl

        self.useragent = useragent
        self.url = url.rstrip("/") + "/"
        self.connector = connector

    @utils.cached_property
    def parsed_url(self):
        return urlparse.urlparse(self.url)

    async def request(self, method, path, **kwargs):
        url = self.url
        if path:
            url = urlparse.urljoin(str(self.url), path)

        more = dict(self._settings)
        more.update(kwargs)

        # XXX: This is a temporary hack to pin-point bad refactoring.
        assert self.connector is not None
        async with self._session as session:
            return await http.request(method, url, session=session, **more)

    @property
    def _session(self):
        """Return a new session for requests."""

        return aiohttp.ClientSession(
            connector=self.connector,
            connector_owner=False,
            # TODO use `raise_for_status=true`, though this needs traces first,
        )

    def get_default_headers(self):
        return {
            "User-Agent": self.useragent,
            "Content-Type": "application/xml; charset=UTF-8",
        }


class DAVStorage(Storage):
    # the file extension of items. Useful for testing against radicale.
    fileext: str
    # mimetype of items
    item_mimetype: str

    @property
    @abstractmethod
    def get_multi_template(self) -> str:
        """XML to use when fetching multiple hrefs."""

    @property
    @abstractmethod
    def get_multi_data_query(self) -> str:
        """LXML query for extracting results in get_multi."""

    @property
    @abstractmethod
    def discovery_class(self) -> Type[Discover]:
        """Discover subclass to use."""

    # The DAVSession class to use
    session_class = DAVSession

    connector: aiohttp.TCPConnector

    _repr_attributes = ["username", "url"]

    _property_table = {
        "displayname": ("displayname", "DAV:"),
    }

    def __init__(self, *, connector, **kwargs):
        # defined for _repr_attributes
        self.username = kwargs.get("username")
        self.url = kwargs.get("url")
        self.connector = connector

        self.session, kwargs = self.session_class.init_and_remaining_args(
            connector=connector,
            **kwargs,
        )
        super().__init__(**kwargs)

    __init__.__signature__ = signature(session_class.__init__)  # type: ignore
    # See  https://github.com/python/mypy/issues/5958

    @classmethod
    async def discover(cls, **kwargs):
        session, _ = cls.session_class.init_and_remaining_args(**kwargs)
        d = cls.discovery_class(session, kwargs)

        async for collection in d.discover():
            yield collection

    @classmethod
    async def create_collection(cls, collection, **kwargs):
        session, _ = cls.session_class.init_and_remaining_args(**kwargs)
        d = cls.discovery_class(session, kwargs)
        return await d.create(collection)

    def _normalize_href(self, *args, **kwargs):
        return _normalize_href(self.session.url, *args, **kwargs)

    def _get_href(self, item):
        href = utils.generate_href(item.ident)
        return self._normalize_href(href + self.fileext)

    def _is_item_mimetype(self, mimetype):
        return _fuzzy_matches_mimetype(self.item_mimetype, mimetype)

    async def get(self, href: str):
        ((actual_href, item, etag),) = await aiostream.stream.list(
            self.get_multi([href])
        )
        assert href == actual_href
        return item, etag

    async def get_multi(self, hrefs):
        hrefs = set(hrefs)
        href_xml = []
        for href in hrefs:
            if href != self._normalize_href(href):
                raise exceptions.NotFoundError(href)
            href_xml.append(f"<href>{href}</href>")
        if href_xml:
            data = self.get_multi_template.format(hrefs="\n".join(href_xml)).encode(
                "utf-8"
            )
            response = await self.session.request(
                "REPORT", "", data=data, headers=self.session.get_default_headers()
            )
            root = _parse_xml(
                await response.content.read()
            )  # etree only can handle bytes
            rv = []
            hrefs_left = set(hrefs)
            for href, etag, prop in self._parse_prop_responses(root):
                raw = prop.find(self.get_multi_data_query)
                if raw is None:
                    dav_logger.warning(f"Skipping {href}, the item content is missing.")
                    continue

                raw = raw.text or ""

                if isinstance(raw, bytes):
                    raw = raw.decode(response.encoding)
                if isinstance(etag, bytes):
                    etag = etag.decode(response.encoding)

                try:
                    hrefs_left.remove(href)
                except KeyError:
                    if href in hrefs:
                        dav_logger.warning(f"Server sent item twice: {href}")
                    else:
                        dav_logger.warning(f"Server sent unsolicited item: {href}")
                else:
                    rv.append((href, Item(raw), etag))
            for href in hrefs_left:
                raise exceptions.NotFoundError(href)

            for href, item, etag in rv:
                yield href, item, etag

    async def _put(self, href, item, etag):
        headers = self.session.get_default_headers()
        headers["Content-Type"] = self.item_mimetype
        if etag is None:
            headers["If-None-Match"] = "*"
        else:
            headers["If-Match"] = etag

        response = await self.session.request(
            "PUT", href, data=item.raw.encode("utf-8"), headers=headers
        )

        await _assert_multistatus_success(response)

        # The server may not return an etag under certain conditions:
        #
        #   An origin server MUST NOT send a validator header field (Section
        #   7.2), such as an ETag or Last-Modified field, in a successful
        #   response to PUT unless the request's representation data was saved
        #   without any transformation applied to the body (i.e., the
        #   resource's new representation data is identical to the
        #   representation data received in the PUT request) and the validator
        #   field value reflects the new representation.
        #
        # -- https://tools.ietf.org/html/rfc7231#section-4.3.4
        #
        # In such cases we return a constant etag. The next synchronization
        # will then detect an etag change and will download the new item.
        etag = response.headers.get("etag", None)
        href = self._normalize_href(str(response.url))
        return href, etag

    async def update(self, href, item, etag):
        if etag is None:
            raise ValueError("etag must be given and must not be None.")
        href, etag = await self._put(self._normalize_href(href), item, etag)
        return etag

    async def upload(self, item: Item):
        href = self._get_href(item)
        rv = await self._put(href, item, None)
        return rv

    async def delete(self, href, etag):
        href = self._normalize_href(href)
        headers = self.session.get_default_headers()
        if etag:  # baikal doesn't give us an etag.
            dav_logger.warning("Deleting an item with no etag.")
            headers.update({"If-Match": etag})

        await self.session.request("DELETE", href, headers=headers)

    def _parse_prop_responses(self, root, handled_hrefs=None):
        if handled_hrefs is None:
            handled_hrefs = set()
        for response in root.iter("{DAV:}response"):
            href = response.find("{DAV:}href")
            if href is None:
                dav_logger.error("Skipping response, href is missing.")
                continue

            href = self._normalize_href(href.text)

            if href in handled_hrefs:
                # Servers that send duplicate hrefs:
                # - Zimbra
                #   https://github.com/pimutils/vdirsyncer/issues/88
                # - Davmail
                #   https://github.com/pimutils/vdirsyncer/issues/144
                dav_logger.warning(f"Skipping identical href: {href!r}")
                continue

            props = response.findall("{DAV:}propstat/{DAV:}prop")
            if props is None or not len(props):
                dav_logger.debug(f"Skipping {href!r}, properties are missing.")
                continue
            else:
                props = _merge_xml(props)

            if props.find("{DAV:}resourcetype/{DAV:}collection") is not None:
                dav_logger.debug(f"Skipping {href!r}, is collection.")
                continue

            etag = getattr(props.find("{DAV:}getetag"), "text", "")
            if not etag:
                dav_logger.debug(f"Skipping {href!r}, etag property is missing.")
                continue

            contenttype = getattr(props.find("{DAV:}getcontenttype"), "text", None)
            if not self._is_item_mimetype(contenttype):
                dav_logger.debug(
                    "Skipping {!r}, {!r} != {!r}.".format(
                        href, contenttype, self.item_mimetype
                    )
                )
                continue

            handled_hrefs.add(href)
            yield href, etag, props

    async def list(self):
        headers = self.session.get_default_headers()
        headers["Depth"] = "1"

        data = b"""<?xml version="1.0" encoding="utf-8" ?>
            <propfind xmlns="DAV:">
                <prop>
                    <resourcetype/>
                    <getcontenttype/>
                    <getetag/>
                </prop>
            </propfind>
            """

        # We use a PROPFIND request instead of addressbook-query due to issues
        # with Zimbra. See https://github.com/pimutils/vdirsyncer/issues/83
        response = await self.session.request(
            "PROPFIND",
            "",
            data=data,
            headers=headers,
        )
        root = _parse_xml(await response.content.read())

        rv = self._parse_prop_responses(root)
        for href, etag, _prop in rv:
            yield href, etag

    async def get_meta(self, key) -> Optional[str]:
        try:
            tagname, namespace = self._property_table[key]
        except KeyError:
            raise exceptions.UnsupportedMetadataError()

        xpath = f"{{{namespace}}}{tagname}"
        body = f"""<?xml version="1.0" encoding="utf-8" ?>
            <propfind xmlns="DAV:">
                <prop>
                    {etree.tostring(etree.Element(xpath), encoding="unicode")}
                </prop>
            </propfind>
        """
        data = body.encode("utf-8")

        headers = self.session.get_default_headers()
        headers["Depth"] = "0"

        response = await self.session.request(
            "PROPFIND",
            "",
            data=data,
            headers=headers,
        )

        root = _parse_xml(await response.content.read())

        for prop in root.findall(".//" + xpath):
            text = normalize_meta_value(getattr(prop, "text", None))
            if text:
                return text
        return None

    async def set_meta(self, key, value):
        try:
            tagname, namespace = self._property_table[key]
        except KeyError:
            raise exceptions.UnsupportedMetadataError()

        lxml_selector = f"{{{namespace}}}{tagname}"
        element = etree.Element(lxml_selector)
        if value is None:
            action = "remove"
        else:
            element.text = normalize_meta_value(value)
            action = "set"

        data = """<?xml version="1.0" encoding="utf-8" ?>
            <propertyupdate xmlns="DAV:">
                <{action}>
                    <prop>
                        {}
                    </prop>
                </{action}>
            </propertyupdate>
        """.format(
            etree.tostring(element, encoding="unicode"),
            action=action,
        ).encode(
            "utf-8"
        )

        await self.session.request(
            "PROPPATCH",
            "",
            data=data,
            headers=self.session.get_default_headers(),
        )

        # XXX: Response content is currently ignored. Though exceptions are
        # raised for HTTP errors, a multistatus with errorcodes inside is not
        # parsed yet. Not sure how common those are, or how they look like. It
        # might be easier (and safer in case of a stupid server) to just issue
        # a PROPFIND to see if the value got actually set.


class CalDAVStorage(DAVStorage):
    storage_name = "caldav"
    fileext = ".ics"
    item_mimetype = "text/calendar"
    discovery_class = CalDiscover

    start_date = None
    end_date = None

    get_multi_template = """<?xml version="1.0" encoding="utf-8" ?>
        <C:calendar-multiget xmlns="DAV:"
            xmlns:C="urn:ietf:params:xml:ns:caldav">
            <prop>
                <getetag/>
                <C:calendar-data/>
            </prop>
            {hrefs}
        </C:calendar-multiget>"""

    get_multi_data_query = "{urn:ietf:params:xml:ns:caldav}calendar-data"

    _property_table = dict(DAVStorage._property_table)
    _property_table.update(
        {
            "color": ("calendar-color", "http://apple.com/ns/ical/"),
            "description": ("calendar-description", "urn:ietf:params:xml:ns:caldav"),
            "order": ("calendar-order", "http://apple.com/ns/ical/"),
        }
    )

    def __init__(self, start_date=None, end_date=None, item_types=(), **kwargs):
        super().__init__(**kwargs)
        if not isinstance(item_types, (list, tuple)):
            raise exceptions.UserError("item_types must be a list.")

        self.item_types = tuple(item_types)
        if (start_date is None) != (end_date is None):
            raise exceptions.UserError(
                "If start_date is given, " "end_date has to be given too."
            )
        elif start_date is not None and end_date is not None:
            namespace = dict(datetime.__dict__)
            namespace["start_date"] = self.start_date = (
                eval(start_date, namespace)
                if isinstance(start_date, (bytes, str))
                else start_date
            )
            self.end_date = (
                eval(end_date, namespace)
                if isinstance(end_date, (bytes, str))
                else end_date
            )

    @staticmethod
    def _get_list_filters(components, start, end):
        if components:
            caldavfilter = """
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="{component}">
                        {timefilter}
                    </C:comp-filter>
                </C:comp-filter>
                """

            if start is not None and end is not None:
                start = start.strftime(CALDAV_DT_FORMAT)
                end = end.strftime(CALDAV_DT_FORMAT)

                timefilter = '<C:time-range start="{start}" end="{end}"/>'.format(
                    start=start, end=end
                )
            else:
                timefilter = ""

            for component in components:
                yield caldavfilter.format(component=component, timefilter=timefilter)
        else:
            if start is not None and end is not None:
                yield from CalDAVStorage._get_list_filters(
                    ("VTODO", "VEVENT"), start, end
                )

    async def list(self):
        caldavfilters = list(
            self._get_list_filters(self.item_types, self.start_date, self.end_date)
        )
        if not caldavfilters:
            # If we don't have any filters (which is the default), taking the
            # risk of sending a calendar-query is not necessary. There doesn't
            # seem to be a widely-usable way to send calendar-queries with the
            # same semantics as a PROPFIND request... so why not use PROPFIND
            # instead?
            #
            # See https://github.com/dmfs/tasks/issues/118 for backstory.
            async for href, etag in super().list():
                yield href, etag

        data = """<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns="DAV:"
                xmlns:C="urn:ietf:params:xml:ns:caldav">
                <prop>
                    <getcontenttype/>
                    <getetag/>
                </prop>
                <C:filter>
                {caldavfilter}
                </C:filter>
            </C:calendar-query>"""

        headers = self.session.get_default_headers()
        # https://github.com/pimutils/vdirsyncer/issues/166
        # The default in CalDAV's calendar-queries is 0, but the examples use
        # an explicit value of 1 for querying items. it is extremely unclear in
        # the spec which values from WebDAV are actually allowed.
        headers["Depth"] = "1"

        handled_hrefs = set()

        for caldavfilter in caldavfilters:
            xml = data.format(caldavfilter=caldavfilter).encode("utf-8")
            response = await self.session.request(
                "REPORT",
                "",
                data=xml,
                headers=headers,
            )
            root = _parse_xml(await response.content.read())
            rv = self._parse_prop_responses(root, handled_hrefs)
            for href, etag, _prop in rv:
                yield href, etag


class CardDAVStorage(DAVStorage):
    storage_name = "carddav"
    fileext = ".vcf"
    item_mimetype = "text/vcard"
    discovery_class = CardDiscover

    get_multi_template = """<?xml version="1.0" encoding="utf-8" ?>
            <C:addressbook-multiget xmlns="DAV:"
                    xmlns:C="urn:ietf:params:xml:ns:carddav">
                <prop>
                    <getetag/>
                    <C:address-data/>
                </prop>
                {hrefs}
            </C:addressbook-multiget>"""

    get_multi_data_query = "{urn:ietf:params:xml:ns:carddav}address-data"

    _property_table = dict(DAVStorage._property_table)
    _property_table.update(
        {
            "description": (
                "addressbook-description",
                "urn:ietf:params:xml:ns:carddav",
            ),
        }
    )
