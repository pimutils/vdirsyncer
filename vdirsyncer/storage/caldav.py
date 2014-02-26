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

CALDAV_LIST_TEMPLATE = 

CALDAV_GET_MULTI_TEMPLATE = ''''''

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'

class CaldavStorage(Storage):
    '''hrefs are full URLs to items'''
    def __init__(self, url, username, password, start_date=None, end_date=None,
                 verify=True, auth='basic', useragent='vdirsyncer', **kwargs):
        '''
        :param url: Direct URL for the CalDAV collection. No autodiscovery.
        :param username: Username for authentication.
        :param password: Password for authentication.
        :param start_date: Start date of timerange to show, default now.
        :param end_date: End date of timerange to show, default now + one year.
        :param verify: Verify SSL certificate, default True.
        :param auth: Authentication method, from {'basic', 'digest'}, default 'basic'.
        :param useragent: Default 'vdirsyncer'.
        '''
        super(CaldavStorage, self).__init__(**kwargs)

        self.session = requests.session()
        self._settings = {'verify': verify}
        if auth == 'basic':
            self._settings['auth'] = (username, password)
        elif auth == 'digest':
            from requests.auth import HTTPDigestAuth
            self._settings['auth'] = HTTPDigestAuth(username, password)
        else:
            raise ValueError('Unknown authentication method: {}'.format(auth))

        self.useragent = useragent
        self.url = url
        self.start_date = start_date
        self.end_date = end_date

        headers = self._default_headers()
        headers['Depth'] = 1
        response = self.session.request(
            'OPTIONS',
            self.url,
            headers=headers,
            **self._settings
        )
        response.raise_for_status()
        if 'calendar-access' not in response.headers['DAV']:
            raise exceptions.StorageError('URL is not a CalDAV collection')

    def _default_headers(self):
        return {
            'User-Agent': self.useragent,
            'Content-Type': 'application/xml; charset=UTF-8'
        }

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
        if not start or not end:
            start = start or datetime.datetime.utcnow()
            end = end or start + datetime.timedelta(years=1)
            caldavfilter = ('<C:comp-filter name="VTODO">'
                            '<C:time-range start="{start}" end="{end}"/>'
                            '</C:comp-filter>').format(start=start.strftime(CALDAV_DT_FORMAT),
                                                       end=end.strftime(CALDAV_DT_FORMAT))
            data = data.format(caldavfilter=caldavfilter)
        else:
            data = data.format(caldavfilter='')
            
        response = self.session.request(
            'REPORT',
            self.url,
            data=data,
            headers=self._default_headers(),
            **self._settings
        )
        response.raise_for_status()
        root = etree.XML(response.content)
        for element in root.iter('{DAV:}response'):
            etag = element.find('{DAV:}propstat').find('{DAV:}prop').find('{DAV:}getetag').text
            href = element.find('{DAV:}href').text
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
        hrefs = '\n'.join('<D:href>{}</D:href>'.format(href=href) for href in hrefs)
        data = data.format(hrefs=hrefs)
        response = self.session.request(
            'REPORT',
            self.url,
            data=data,
            headers=self._default_headers(),
            **self._settings
        )
        if response != 404:  # nonexisting hrefs will be handled separately
            response.raise_for_status()
        root = etree.XML(response.content)
        finished_hrefs = set()
        rv = []
        for element in root.iter('{DAV:}response'):
            try:
                href = element.find('{DAV:}href').text
                obj = element \
                    .find('{DAV:}propstat') \
                    .find('{DAV:}prop') \
                    .find('{urn:ietf:params:xml:ns:caldav}calendar-data').text
                etag = element \
                    .find('{DAV:}propstat') \
                    .find('{DAV:}prop') \
                    .find('{DAV:}getetag').text
            except AttributeError:
                continue
            rv.append((href, Item(obj), etag))
            finished_hrefs.add(href)
        for href in set(hrefs) - finished_hrefs:
            raise exceptions.NotFoundError(href)
        return rv

    def get(self, href):
        ((actual_href, obj, etag),) = self.get_multi([href])
        assert href == actual_href
        return obj, etag

    def has(self, href):
        try:
            self.get(href)
        except exceptions.NotFoundError:
            return False
        else:
            return True

    def upload(self, obj):
        href = self.url + self._get_href(obj.uid)
        headers = self._default_headers()
        headers.update({
            'Content-Type': 'text/calendar',
            'If-None-Match': '*'
        })
        response = requests.put(
            href,
            data=obj.raw
            headers=headers,
            **self._settings
        )
        response.raise_for_status()

        if not response.headers.get('etag', None):
            obj2, etag = self.get(href)
            assert obj2.raw == obj.raw
        return href, etag

    def update(self, href, obj, etag):
        headers = self._default_headers()
        headers.update({
            'Content-Type': 'text/calendar',
            'If-Match': etag
        })
        response = requests.put(
            remotepath,
            data=obj.raw,
            headers=headers,
            **self._settings
        )
        response.raise_for_status()
        
        if not response.headers.get('etag', None):
            obj2, etag = self.get(href)
            assert obj2.raw == obj.raw
        return href, etag
