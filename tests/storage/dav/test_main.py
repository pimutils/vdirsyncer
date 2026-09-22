from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest
from multidict import CIMultiDict
from yarl import URL

from vdirsyncer.storage.dav import _BAD_XML_CHARS
from vdirsyncer.storage.dav import CardDAVStorage
from vdirsyncer.storage.dav import _merge_xml
from vdirsyncer.storage.dav import _normalize_href
from vdirsyncer.storage.dav import _parse_xml


def test_xml_utilities():
    x = _parse_xml(
        b"""<?xml version="1.0" encoding="UTF-8" ?>
        <multistatus xmlns="DAV:">
            <response>
                <propstat>
                    <status>HTTP/1.1 404 Not Found</status>
                    <prop>
                        <getcontenttype/>
                    </prop>
                </propstat>
                <propstat>
                    <prop>
                        <resourcetype>
                            <collection/>
                        </resourcetype>
                    </prop>
                </propstat>
            </response>
        </multistatus>
    """
    )

    response = x.find("{DAV:}response")
    props = _merge_xml(response.findall("{DAV:}propstat/{DAV:}prop"))
    assert props.find("{DAV:}resourcetype/{DAV:}collection") is not None
    assert props.find("{DAV:}getcontenttype") is not None


@pytest.mark.parametrize("char", range(32))
def test_xml_specialchars(char):
    x = _parse_xml(
        '<?xml version="1.0" encoding="UTF-8" ?>'
        f"<foo>ye{chr(char)}s\r\n"
        "hello</foo>".encode("ascii")
    )

    if char in _BAD_XML_CHARS:
        assert x.text == "yes\nhello"


@pytest.mark.parametrize(
    "href",
    [
        "/dav/calendars/user/testuser/123/UID%253A20210609T084907Z-@synaps-web-54fddfdf7-7kcfm%250A.ics",
    ],
)
def test_normalize_href(href):
    assert href == _normalize_href("https://example.com", href)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("location", "expected_href"),
    [
        (
            "https://example.com/lists/default/server-assigned.vcf",
            "/lists/default/server-assigned.vcf",
        ),
        ("/lists/default/server-assigned.vcf", "/lists/default/server-assigned.vcf"),
        ("server-assigned.vcf", "/lists/redirected/server-assigned.vcf"),
        ("./server-assigned.vcf", "/lists/redirected/server-assigned.vcf"),
        ("../server-assigned.vcf", "/lists/server-assigned.vcf"),
        ("server%20assigned.vcf", "/lists/redirected/server%20assigned.vcf"),
        ("?version=2", "/lists/redirected/requested.vcf"),
        (None, "/lists/redirected/requested.vcf"),
        ("", "/lists/redirected/requested.vcf"),
    ],
)
async def test_put_uses_server_assigned_location(location, expected_href):
    storage = CardDAVStorage(
        connector=None,
        url="https://example.com/lists/default/",
    )
    # The PUT may have followed a redirect outside the configured collection.
    response = Mock(
        headers=CIMultiDict(
            {
                "ETag": '"new"',
                **({"Location": location} if location is not None else {}),
            }
        ),
        url=URL("https://example.com/lists/redirected/requested.vcf"),
    )
    response.content.read = AsyncMock(return_value=b"")
    storage.session.request = AsyncMock(return_value=response)

    href, etag = await storage._put(
        "/lists/default/requested.vcf",
        Mock(raw="BEGIN:VCARD\nEND:VCARD"),
        None,
    )

    assert href == expected_href
    assert etag == '"new"'
