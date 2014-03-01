# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.dav.caldav
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Original version from khal: https://github.com/geier/khal

    :copyright: (c) 2014 Markus Unterwaditzer, Christian Geier and contributors
    :license: MIT, see LICENSE for more details.
'''

from .base import DavStorage
from ..base import Item
import vdirsyncer.exceptions as exceptions
from lxml import etree
import datetime

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'
CONFIG_DT_FORMAT = '%Y-%m-%d'


class CaldavStorage(DavStorage):

    fileext = '.ics'
    start_date = None
    end_date = None

    def __init__(self, start_date=None, end_date=None, **kwargs):
        '''
        :param start_date: Start date of timerange to show, default -inf.
        :param end_date: End date of timerange to show, default +inf.
        '''
        super(CaldavStorage, self).__init__(**kwargs)
        if (start_date is None) != (end_date is None):
            raise ValueError('If start_date is given, '
                             'end_date has to be given too.')
        elif start_date is not None and end_date is not None:
            namespace = dict(datetime.__dict__)
            namespace['start_date'] = self.start_date = \
                (eval(start_date, namespace) if isinstance(start_date, str)
                 else start_date)
            self.end_date = \
                (eval(end_date, namespace) if isinstance(end_date, str)
                 else end_date)

        headers = self._default_headers()
        headers['Depth'] = 1
        response = self._request(
            'OPTIONS',
            '',
            headers=headers
        )
        response.raise_for_status()
        if 'calendar-access' not in response.headers.get('DAV', ''):
            raise exceptions.StorageError('URL is not a CalDAV collection')

    def _default_headers(self):
        return {
            'User-Agent': self.useragent,
            'Content-Type': 'application/xml; charset=UTF-8'
        }

    def list(self):
        data = '''<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:"
                xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <D:getetag/>
                    </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        {caldavfilter}
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>'''
        start = self.start_date
        end = self.end_date
        if start and end:
            start = start.strftime(CALDAV_DT_FORMAT)
            end = end.strftime(CALDAV_DT_FORMAT)
            caldavfilter = ('<C:comp-filter name="VTODO">'
                            '<C:time-range start="{start}" end="{end}"/>'
                            '</C:comp-filter>').format(start=start,
                                                       end=end)
            data = data.format(caldavfilter=caldavfilter)
        else:
            data = data.format(caldavfilter='')

        response = self._request(
            'REPORT',
            '',
            data=data,
            headers=self._default_headers()
        )
        response.raise_for_status()
        root = etree.XML(response.content)
        for element in root.iter('{DAV:}response'):
            etag = element.find('{DAV:}propstat').find(
                '{DAV:}prop').find('{DAV:}getetag').text
            href = self._simplify_href(element.find('{DAV:}href').text)
            yield href, etag

    def get_multi(self, hrefs):
        if not hrefs:
            return ()

        data = '''<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-multiget xmlns:D="DAV:"
                xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <D:getetag/>
                    <C:calendar-data/>
                </D:prop>
                {hrefs}
            </C:calendar-multiget>'''
        href_xml = []
        for href in hrefs:
            assert '/' not in href, href
            href_xml.append('<D:href>{}</D:href>'.format(self.url + href))
        data = data.format(hrefs='\n'.join(href_xml))
        response = self._request(
            'REPORT',
            '',
            data=data,
            headers=self._default_headers()
        )
        response.raise_for_status()
        root = etree.XML(response.content)  # etree only can handle bytes
        rv = []
        hrefs_left = set(hrefs)
        for element in root.iter('{DAV:}response'):
            href = self._simplify_href(
                element.find('{DAV:}href').text.decode(response.encoding))
            obj = element \
                .find('{DAV:}propstat') \
                .find('{DAV:}prop') \
                .find('{urn:ietf:params:xml:ns:caldav}calendar-data').text
            etag = element \
                .find('{DAV:}propstat') \
                .find('{DAV:}prop') \
                .find('{DAV:}getetag').text
            if isinstance(obj, bytes):
                obj = obj.decode(response.encoding)
            if isinstance(etag, bytes):
                etag = etag.decode(response.encoding)
            rv.append((href, Item(obj), etag))
            hrefs_left.remove(href)
        for href in hrefs_left:
            raise exceptions.NotFoundError(href)
        return rv

    def has(self, href):
        try:
            self.get(href)
        except exceptions.PreconditionFailed:
            return False
        else:
            return True

    def upload(self, obj):
        href = self._get_href(obj.uid)
        headers = self._default_headers()
        headers.update({
            'Content-Type': 'text/calendar',
            'If-None-Match': '*'
        })
        response = self._request(
            'PUT',
            href,
            data=obj.raw,
            headers=headers
        )
        self._check_response(response)

        etag = response.headers.get('etag', None)
        if not etag:
            obj2, etag = self.get(href)
            assert obj2.raw == obj.raw
        return href, etag

    def update(self, href, obj, etag):
        headers = self._default_headers()
        headers.update({
            'Content-Type': 'text/calendar',
            'If-Match': etag
        })
        response = self._request(
            'PUT',
            href,
            data=obj.raw,
            headers=headers
        )
        self._check_response(response)

        etag = response.headers.get('etag', None)
        if not etag:
            obj2, etag = self.get(href)
            assert obj2.raw == obj.raw
        return href, etag

    def delete(self, href, etag):
        headers = self._default_headers()
        headers.update({
            'If-Match': etag
        })

        response = self._request(
            'DELETE',
            href,
            headers=headers
        )
        self._check_response(response)
