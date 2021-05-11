import datetime
import logging
import urllib.parse as urlparse
import xml.etree.ElementTree as etree
from inspect import getfullargspec
from inspect import signature

import requests
from requests.exceptions import HTTPError

from .. import exceptions
from .. import http
from .. import utils
from ..http import prepare_auth
from ..http import prepare_client_cert
from ..http import prepare_verify
from ..http import USERAGENT
from ..vobject import Item
from .base import normalize_meta_value
from .base import Storage


dav_logger = logging.getLogger(__name__)

CALDAV_DT_FORMAT = "%Y%m%dT%H%M%SZ"


def _generate_path_reserved_chars():
    for x in "/?#[]!$&'()*+,;":
        x = urlparse.quote(x, "")
        yield x.upper()
        yield x.lower()


_path_reserved_chars = frozenset(_generate_path_reserved_chars())
del _generate_path_reserved_chars


def _contains_quoted_reserved_chars(x):
    for y in _path_reserved_chars:
        if y in x:
            dav_logger.debug(f"Unsafe character: {y!r}")
            return True
    return False


def _assert_multistatus_success(r):
    # Xandikos returns a multistatus on PUT.
    try:
        root = _parse_xml(r.content)
    except InvalidXMLResponse:
        return
    for status in root.findall(".//{DAV:}status"):
        parts = status.text.strip().split()
        try:
            st = int(parts[1])
        except (ValueError, IndexError):
            continue
        if st < 200 or st >= 400:
            raise HTTPError(f"Server error: {st}")


def _normalize_href(base, href):
    """Normalize the href to be a path only relative to hostname and
    schema."""
    orig_href = href
    if not href:
        raise ValueError(href)

    x = urlparse.urljoin(base, href)
    x = urlparse.urlsplit(x).path

    # Encoding issues:
    # - https://github.com/owncloud/contacts/issues/581
    # - https://github.com/Kozea/Radicale/issues/298
    old_x = None
    while old_x is None or x != old_x:
        if _contains_quoted_reserved_chars(x):
            break
        old_x = x
        x = urlparse.unquote(x)

    x = urlparse.quote(x, "/@%:")

    if orig_href == x:
        dav_logger.debug(f"Already normalized: {x!r}")
    else:
        dav_logger.debug("Normalized URL from {!r} to {!r}".format(orig_href, x))

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
    _namespace = None
    _resourcetype = None
    _homeset_xml = None
    _homeset_tag = None
    _well_known_uri = None
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

    def find_principal(self):
        try:
            return self._find_principal_impl("")
        except (HTTPError, exceptions.Error):
            dav_logger.debug("Trying out well-known URI")
            return self._find_principal_impl(self._well_known_uri)

    def _find_principal_impl(self, url):
        headers = self.session.get_default_headers()
        headers["Depth"] = "0"
        body = b"""
        <propfind xmlns="DAV:">
            <prop>
                <current-user-principal />
            </prop>
        </propfind>
        """

        response = self.session.request("PROPFIND", url, headers=headers, data=body)

        root = _parse_xml(response.content)
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
        return urlparse.urljoin(response.url, rv.text).rstrip("/") + "/"

    def find_home(self):
        url = self.find_principal()
        headers = self.session.get_default_headers()
        headers["Depth"] = "0"
        response = self.session.request(
            "PROPFIND", url, headers=headers, data=self._homeset_xml
        )

        root = etree.fromstring(response.content)
        # Better don't do string formatting here, because of XML namespaces
        rv = root.find(".//" + self._homeset_tag + "/{DAV:}href")
        if rv is None:
            raise InvalidXMLResponse("Couldn't find home-set.")
        return urlparse.urljoin(response.url, rv.text).rstrip("/") + "/"

    def find_collections(self):
        rv = None
        try:
            rv = list(self._find_collections_impl(""))
        except (HTTPError, exceptions.Error):
            pass

        if rv:
            return rv
        dav_logger.debug("Given URL is not a homeset URL")
        return self._find_collections_impl(self.find_home())

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

    def _find_collections_impl(self, url):
        headers = self.session.get_default_headers()
        headers["Depth"] = "1"
        r = self.session.request(
            "PROPFIND", url, headers=headers, data=self._collection_xml
        )
        root = _parse_xml(r.content)
        done = set()
        for response in root.findall("{DAV:}response"):
            if not self._check_collection_resource_type(response):
                continue

            href = response.find("{DAV:}href")
            if href is None:
                raise InvalidXMLResponse("Missing href tag for collection " "props.")
            href = urlparse.urljoin(r.url, href.text)
            if href not in done:
                done.add(href)
                yield {"href": href}

    def discover(self):
        for c in self.find_collections():
            url = c["href"]
            collection = self._get_collection_from_url(url)
            storage_args = dict(self.kwargs)
            storage_args.update({"url": url, "collection": collection})
            yield storage_args

    def create(self, collection):
        if collection is None:
            collection = self._get_collection_from_url(self.kwargs["url"])

        for c in self.discover():
            if c["collection"] == collection:
                return c

        home = self.find_home()
        url = urlparse.urljoin(home, urlparse.quote(collection, "/@"))

        try:
            url = self._create_collection_impl(url)
        except HTTPError as e:
            raise NotImplementedError(e)
        else:
            rv = dict(self.kwargs)
            rv["collection"] = collection
            rv["url"] = url
            return rv

    def _create_collection_impl(self, url):
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

        response = self.session.request(
            "MKCOL",
            url,
            data=data,
            headers=self.session.get_default_headers(),
        )
        return response.url


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
    _resourcetype = "{%s}addressbook" % _namespace
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
    """
    A helper class to connect to DAV servers.
    """

    @classmethod
    def init_and_remaining_args(cls, **kwargs):
        argspec = getfullargspec(cls.__init__)
        self_args, remainder = utils.split_dict(kwargs, argspec.args.__contains__)

        return cls(**self_args), remainder

    def __init__(
        self,
        url,
        username="",
        password="",
        verify=True,
        auth=None,
        useragent=USERAGENT,
        verify_fingerprint=None,
        auth_cert=None,
    ):
        self._settings = {
            "cert": prepare_client_cert(auth_cert),
            "auth": prepare_auth(auth, username, password),
        }
        self._settings.update(prepare_verify(verify, verify_fingerprint))

        self.useragent = useragent
        self.url = url.rstrip("/") + "/"

        self._session = requests.session()

    @utils.cached_property
    def parsed_url(self):
        return urlparse.urlparse(self.url)

    def request(self, method, path, **kwargs):
        url = self.url
        if path:
            url = urlparse.urljoin(self.url, path)

        more = dict(self._settings)
        more.update(kwargs)
        return http.request(method, url, session=self._session, **more)

    def get_default_headers(self):
        return {
            "User-Agent": self.useragent,
            "Content-Type": "application/xml; charset=UTF-8",
        }


class DAVStorage(Storage):
    # the file extension of items. Useful for testing against radicale.
    fileext = None
    # mimetype of items
    item_mimetype = None
    # XML to use when fetching multiple hrefs.
    get_multi_template = None
    # The LXML query for extracting results in get_multi
    get_multi_data_query = None
    # The Discover subclass to use
    discovery_class = None
    # The DAVSession class to use
    session_class = DAVSession

    _repr_attributes = ("username", "url")

    _property_table = {
        "displayname": ("displayname", "DAV:"),
    }

    def __init__(self, **kwargs):
        # defined for _repr_attributes
        self.username = kwargs.get("username")
        self.url = kwargs.get("url")

        self.session, kwargs = self.session_class.init_and_remaining_args(**kwargs)
        super().__init__(**kwargs)

    __init__.__signature__ = signature(session_class.__init__)

    @classmethod
    def discover(cls, **kwargs):
        session, _ = cls.session_class.init_and_remaining_args(**kwargs)
        d = cls.discovery_class(session, kwargs)
        return d.discover()

    @classmethod
    def create_collection(cls, collection, **kwargs):
        session, _ = cls.session_class.init_and_remaining_args(**kwargs)
        d = cls.discovery_class(session, kwargs)
        return d.create(collection)

    def _normalize_href(self, *args, **kwargs):
        return _normalize_href(self.session.url, *args, **kwargs)

    def _get_href(self, item):
        href = utils.generate_href(item.ident)
        return self._normalize_href(href + self.fileext)

    def _is_item_mimetype(self, mimetype):
        return _fuzzy_matches_mimetype(self.item_mimetype, mimetype)

    def get(self, href):
        ((actual_href, item, etag),) = self.get_multi([href])
        assert href == actual_href
        return item, etag

    def get_multi(self, hrefs):
        hrefs = set(hrefs)
        href_xml = []
        for href in hrefs:
            if href != self._normalize_href(href):
                raise exceptions.NotFoundError(href)
            href_xml.append(f"<href>{href}</href>")
        if not href_xml:
            return ()

        data = self.get_multi_template.format(hrefs="\n".join(href_xml)).encode("utf-8")
        response = self.session.request(
            "REPORT", "", data=data, headers=self.session.get_default_headers()
        )
        root = _parse_xml(response.content)  # etree only can handle bytes
        rv = []
        hrefs_left = set(hrefs)
        for href, etag, prop in self._parse_prop_responses(root):
            raw = prop.find(self.get_multi_data_query)
            if raw is None:
                dav_logger.warning(
                    "Skipping {}, the item content is missing.".format(href)
                )
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
                    dav_logger.warning("Server sent item twice: {}".format(href))
                else:
                    dav_logger.warning("Server sent unsolicited item: {}".format(href))
            else:
                rv.append((href, Item(raw), etag))
        for href in hrefs_left:
            raise exceptions.NotFoundError(href)
        return rv

    def _put(self, href, item, etag):
        headers = self.session.get_default_headers()
        headers["Content-Type"] = self.item_mimetype
        if etag is None:
            headers["If-None-Match"] = "*"
        else:
            headers["If-Match"] = etag

        response = self.session.request(
            "PUT", href, data=item.raw.encode("utf-8"), headers=headers
        )

        _assert_multistatus_success(response)

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
        href = self._normalize_href(response.url)
        return href, etag

    def update(self, href, item, etag):
        if etag is None:
            raise ValueError("etag must be given and must not be None.")
        href, etag = self._put(self._normalize_href(href), item, etag)
        return etag

    def upload(self, item):
        href = self._get_href(item)
        return self._put(href, item, None)

    def delete(self, href, etag):
        href = self._normalize_href(href)
        headers = self.session.get_default_headers()
        headers.update({"If-Match": etag})

        self.session.request("DELETE", href, headers=headers)

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
                dav_logger.warning("Skipping identical href: {!r}".format(href))
                continue

            props = response.findall("{DAV:}propstat/{DAV:}prop")
            if props is None or not len(props):
                dav_logger.debug("Skipping {!r}, properties are missing.".format(href))
                continue
            else:
                props = _merge_xml(props)

            if props.find("{DAV:}resourcetype/{DAV:}collection") is not None:
                dav_logger.debug(f"Skipping {href!r}, is collection.")
                continue

            etag = getattr(props.find("{DAV:}getetag"), "text", "")
            if not etag:
                dav_logger.debug(
                    "Skipping {!r}, etag property is missing.".format(href)
                )
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

    def list(self):
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
        response = self.session.request("PROPFIND", "", data=data, headers=headers)
        root = _parse_xml(response.content)

        rv = self._parse_prop_responses(root)
        for href, etag, _prop in rv:
            yield href, etag

    def get_meta(self, key):
        try:
            tagname, namespace = self._property_table[key]
        except KeyError:
            raise exceptions.UnsupportedMetadataError()

        xpath = f"{{{namespace}}}{tagname}"
        data = """<?xml version="1.0" encoding="utf-8" ?>
            <propfind xmlns="DAV:">
                <prop>
                    {}
                </prop>
            </propfind>
        """.format(
            etree.tostring(etree.Element(xpath), encoding="unicode")
        ).encode(
            "utf-8"
        )

        headers = self.session.get_default_headers()
        headers["Depth"] = "0"

        response = self.session.request("PROPFIND", "", data=data, headers=headers)

        root = _parse_xml(response.content)

        for prop in root.findall(".//" + xpath):
            text = normalize_meta_value(getattr(prop, "text", None))
            if text:
                return text
        return ""

    def set_meta(self, key, value):
        try:
            tagname, namespace = self._property_table[key]
        except KeyError:
            raise exceptions.UnsupportedMetadataError()

        lxml_selector = f"{{{namespace}}}{tagname}"
        element = etree.Element(lxml_selector)
        element.text = normalize_meta_value(value)

        data = """<?xml version="1.0" encoding="utf-8" ?>
            <propertyupdate xmlns="DAV:">
                <set>
                    <prop>
                        {}
                    </prop>
                </set>
            </propertyupdate>
        """.format(
            etree.tostring(element, encoding="unicode")
        ).encode(
            "utf-8"
        )

        self.session.request(
            "PROPPATCH", "", data=data, headers=self.session.get_default_headers()
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

    def list(self):
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
            yield from DAVStorage.list(self)

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
            response = self.session.request("REPORT", "", data=xml, headers=headers)
            root = _parse_xml(response.content)
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
