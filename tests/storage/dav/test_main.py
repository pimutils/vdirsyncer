import pytest

from hypothesis import given
import hypothesis.strategies as st

from vdirsyncer.storage.dav import _BAD_XML_CHARS, _merge_xml, _parse_xml, \
    _clean_body


def test_xml_utilities():
    x = _parse_xml(b'''<?xml version="1.0" encoding="UTF-8" ?>
        <D:multistatus xmlns:D="DAV:">
            <D:response>
                <D:propstat>
                    <D:status>HTTP/1.1 404 Not Found</D:status>
                    <D:prop>
                        <D:getcontenttype/>
                    </D:prop>
                </D:propstat>
                <D:propstat>
                    <D:prop>
                        <D:resourcetype>
                            <D:collection/>
                        </D:resourcetype>
                    </D:prop>
                </D:propstat>
            </D:response>
        </D:multistatus>
    ''')

    response = x.find('{DAV:}response')
    props = _merge_xml(response.findall('{DAV:}propstat/{DAV:}prop'))
    assert props.find('{DAV:}resourcetype/{DAV:}collection') is not None
    assert props.find('{DAV:}getcontenttype') is not None


@pytest.mark.parametrize('char', range(32))
def test_xml_specialchars(char):
    char = chr(char).encode('ascii')
    x = _parse_xml(b'<?xml version="1.0" encoding="UTF-8" ?>'
                   b'<foo>ye%ss\r\n'
                   b'hello</foo>' % char)

    if char in _BAD_XML_CHARS:
        assert x.text == 'yes\nhello'
