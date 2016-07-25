from vdirsyncer.storage.dav import _merge_xml, _parse_xml


def test_xml_utilities():
    x = _parse_xml('''<?xml version="1.0" encoding="UTF-8" ?>
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
