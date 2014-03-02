# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.dav.carddav
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Original version from pycarddav: https://github.com/geier/pycarddav

    :copyright: (c) 2014 Markus Unterwaditzer, Christian Geier and contributors
    :license: MIT, see LICENSE for more details.
'''

from .base import DavStorage


class CarddavStorage(DavStorage):

    fileext = '.vcf'
    item_mimetype = 'text/vcard'
    dav_header = 'addressbook'

    get_multi_template = '''<?xml version="1.0" encoding="utf-8" ?>
            <C:addressbook-multiget xmlns:D="DAV:"
                    xmlns:C="urn:ietf:params:xml:ns:carddav">
                <D:prop>
                    <D:getetag/>
                    <C:address-data/>
                </D:prop>
                {hrefs}
            </C:addressbook-multiget>'''

    get_multi_data_query = '{urn:ietf:params:xml:ns:carddav}address-data'

    list_xml = '''<?xml version="1.0" encoding="utf-8" ?>
        <C:addressbook-query xmlns:D="DAV:"
                xmlns:C="urn:ietf:params:xml:ns:carddav">
            <D:prop>
                <D:getetag/>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCARD"/>
            </C:filter>
        </C:addressbook-query>'''
