# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.caldav
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Original version from khal: https://github.com/geier/khal

    :copyright: (c) 2014 Markus Unterwaditzer, Christian Geier and contributors
    :license: MIT, see LICENSE for more details.
'''

from .base import Storage, Item
import vdirsyncer.exceptions as exceptions
from lxml import etree
import requests
import datetime

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'


class CaldavStorage(Storage):

    '''hrefs are full URLs to items'''
    _session = None
    fileext = '.ics'

    def __init__(self, url, username='', password='', start_date=None,
                 end_date=None, verify=True, auth='basic',
                 useragent='vdirsyncer', _request_func=None, **kwargs):
        '''
        :param url: Direct URL for the CalDAV collection. No autodiscovery.
        :param username: Username for authentication.
        :param password: Password for authentication.
        :param start_date: Start date of timerange to show, default now.
        :param end_date: End date of timerange to show, default now + one year.
        :param verify: Verify SSL certificate, default True.
        :param auth: Authentication method, from {'basic', 'digest'}, default 'basic'.
        :param useragent: Default 'vdirsyncer'.
        :param _request_func: Function to use for network calls. Same API as
                              requests.request. Useful for tests.
        '''
        super(CaldavStorage, self).__init__(**kwargs)
        self._request = _request_func or self._request

        self._settings = {'verify': verify}
        if auth == 'basic':
            self._settings['auth'] = (username, password)
        elif auth == 'digest':
            from requests.auth import HTTPDigestAuth
            self._settings['auth'] = HTTPDigestAuth(username, password)
        else:
            raise ValueError('Unknown authentication method: {}'.format(auth))

        self.useragent = useragent
        self.url = url.rstrip('/') + '/'
        self.start_date = start_date
        self.end_date = end_date

        headers = self._default_headers()
        headers['Depth'] = 1
        response = self._request(
            'OPTIONS',
            '',
            headers=headers
        )
        response.raise_for_status()
        if 'calendar-access' not in response.headers['DAV']:
            raise exceptions.StorageError('URL is not a CalDAV collection')

    def _default_headers(self):
        return {
            'User-Agent': self.useragent,
            'Content-Type': 'application/xml; charset=UTF-8'
        }

    def _simplify_href(self, href):
        if href.startswith(self.url):
            return href[len(self.url):]
        return href

    def _request(self, method, item, data=None, headers=None):
        if self._session is None:
            self._session = requests.session()
        assert '/' not in item
        url = self.url + item
        return self._session.request(method, url, data=data, headers=headers, **self._settings)

    @staticmethod
    def _check_response(response):
        if response.status_code == 412:
            raise exceptions.PreconditionFailed()
        response.raise_for_status()

    def list(self):
        data = '''<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
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
        if start or end:
            start = start or datetime.datetime.utcnow()
            end = end or start + datetime.timedelta(days=365)
            caldavfilter = ('<C:comp-filter name="VTODO">'
                            '<C:time-range start="{start}" end="{end}"/>'
                            '</C:comp-filter>').format(start=start.strftime(CALDAV_DT_FORMAT),
                                                       end=end.strftime(CALDAV_DT_FORMAT))
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
<C:calendar-multiget xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <D:getetag/>
        <C:calendar-data/>
    </D:prop>
    {hrefs}
</C:calendar-multiget>'''
        href_xml = []
        for href in hrefs:
            assert '/' not in href
            href_xml.append('<D:href>{}</D:href>'.format(self.url + href))
        data = data.format(hrefs='\n'.join(href_xml))
        response = self._request(
            'REPORT',
            '',
            data=data,
            headers=self._default_headers()
        )
        response.raise_for_status()
        root = etree.XML(response.content)
        rv = []
        hrefs_left = set(hrefs)
        for element in root.iter('{DAV:}response'):
            href = self._simplify_href(element.find('{DAV:}href').text)
            obj = element \
                .find('{DAV:}propstat') \
                .find('{DAV:}prop') \
                .find('{urn:ietf:params:xml:ns:caldav}calendar-data').text
            etag = element \
                .find('{DAV:}propstat') \
                .find('{DAV:}prop') \
                .find('{DAV:}getetag').text
            rv.append((href, Item(obj), etag))
            hrefs_left.remove(href)
        for href in hrefs_left:
            raise exceptions.NotFound(href)
        return rv

    def get(self, href):
        ((actual_href, obj, etag),) = self.get_multi([href])
        assert href == actual_href
        return obj, etag

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
