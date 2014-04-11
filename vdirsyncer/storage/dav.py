# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.dav
    ~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer, Christian Geier and contributors
    :license: MIT, see LICENSE for more details.
'''

from .base import Storage, Item
from .http import prepare_auth, prepare_verify, USERAGENT
from .. import exceptions
from .. import log
from ..utils import get_password, request
import requests
import datetime
import urlparse
from lxml import etree


dav_logger = log.get('storage.dav')

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'
CONFIG_DT_FORMAT = '%Y-%m-%d'


class DavStorage(Storage):

    # the file extension of items. Useful for testing against radicale.
    fileext = None
    # mimetype of items
    item_mimetype = None
    # The expected header for resource validation.
    dav_header = None
    # XML to use when fetching multiple hrefs.
    get_multi_template = None
    # The LXML query for extracting results in get_multi
    get_multi_data_query = None
    # The leif class to use for autodiscovery
    # This should be the class *name* (i.e. "module attribute name") instead of
    # the class, because leif is an optional dependency
    leif_class = None

    _session = None
    _repr_attributes = ('username', 'url')

    def __init__(self, url, username='', password='', collection=None,
                 verify=True, auth=None, useragent=USERAGENT, **kwargs):
        '''
        :param url: Base URL or an URL to a collection. Autodiscovery should be
            done via :py:meth:`DavStorage.discover`.
        :param username: Username for authentication.
        :param password: Password for authentication.
        :param verify: Verify SSL certificate, default True.
        :param auth: Authentication method, from {'basic', 'digest'}, default
            'basic'.
        :param useragent: Default 'vdirsyncer'.
        '''

        super(DavStorage, self).__init__(**kwargs)

        if username and not password:
            password = get_password(username, url)

        self._settings = {
            'verify': prepare_verify(verify),
            'auth': prepare_auth(auth, username, password)
        }
        self.username, self.password = username, password
        self.useragent = useragent

        url = url.rstrip('/') + '/'
        if collection is not None:
            url = urlparse.urljoin(url, collection)
        self.url = url.rstrip('/') + '/'
        self.parsed_url = urlparse.urlparse(self.url)
        self.collection = collection

        headers = self._default_headers()
        headers['Depth'] = 1
        response = self._request(
            'OPTIONS',
            '',
            headers=headers
        )
        response.raise_for_status()
        if self.dav_header not in response.headers.get('DAV', ''):
            raise exceptions.StorageError('URL is not a collection')

    def _default_headers(self):
        return {
            'User-Agent': self.useragent,
            'Content-Type': 'application/xml; charset=UTF-8'
        }

    @classmethod
    def discover(cls, url, **kwargs):
        if kwargs.pop('collection', None) is not None:
            raise TypeError('collection argument must not be given.')
        from leif import leif
        d = getattr(leif, cls.leif_class)(
            url,
            user=kwargs.get('username', None),
            password=kwargs.get('password', None),
            ssl_verify=kwargs.get('verify', True)
        )
        for c in d.discover():
            collection = urlparse.urljoin(url, c['href'])
            if collection.startswith(url):
                collection = collection[len(url):]
            collection = collection.rstrip('/')
            s = cls(url=url, collection=collection, **kwargs)
            s.displayname = c['displayname']
            yield s

    def _normalize_href(self, href):
        '''Normalize the href to be a path only relative to hostname and
        schema.'''
        x = urlparse.urljoin(self.url, href)
        assert x.startswith(self.url)
        return urlparse.urlsplit(x).path

    def _get_href(self, uid):
        return self._normalize_href(super(DavStorage, self)._get_href(uid))

    def _request(self, method, path, data=None, headers=None):
        path = path or self.parsed_url.path
        assert path.startswith(self.parsed_url.path)
        if self._session is None:
            self._session = requests.session()
        url = self.parsed_url.scheme + '://' + self.parsed_url.netloc + path
        return request(method, url, data=data, headers=headers,
                       session=self._session, **self._settings)

    @staticmethod
    def _check_response(response):
        if response.status_code == 412:
            raise exceptions.PreconditionFailed(response.reason)
        response.raise_for_status()

    def get(self, href):
        ((actual_href, item, etag),) = self.get_multi([href])
        assert href == actual_href
        return item, etag

    def get_multi(self, hrefs):
        if not hrefs:
            return ()
        hrefs = [self._normalize_href(href) for href in hrefs]

        href_xml = []
        for href in hrefs:
            href_xml.append('<D:href>{}</D:href>'.format(href))
        data = self.get_multi_template.format(hrefs='\n'.join(href_xml))
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
            href = self._normalize_href(
                element.find('{DAV:}href').text.decode(response.encoding))
            raw = element \
                .find('{DAV:}propstat') \
                .find('{DAV:}prop') \
                .find(self.get_multi_data_query).text
            etag = element \
                .find('{DAV:}propstat') \
                .find('{DAV:}prop') \
                .find('{DAV:}getetag').text
            if isinstance(raw, bytes):
                raw = raw.decode(response.encoding)
            if isinstance(etag, bytes):
                etag = etag.decode(response.encoding)
            rv.append((href, Item(raw), etag))
            try:
                hrefs_left.remove(href)
            except KeyError:
                raise KeyError('{} doesn\'t exist in {}'
                               .format(href, hrefs_left))
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

    def _put(self, href, item, etag):
        headers = self._default_headers()
        headers['Content-Type'] = self.item_mimetype
        if etag is None:
            headers['If-None-Match'] = '*'
        else:
            assert etag[0] == etag[-1] == '"'
            headers['If-Match'] = etag

        response = self._request(
            'PUT',
            href,
            data=item.raw.encode('utf-8'),
            headers=headers
        )
        self._check_response(response)
        etag = response.headers.get('etag', None)
        if not etag:
            item2, etag = self.get(href)
            assert item2.uid == item.uid
        return href, etag

    def update(self, href, item, etag):
        href = self._normalize_href(href)
        if etag is None:
            raise ValueError('etag must be given and must not be None.')
        return self._put(href, item, etag)

    def upload(self, item):
        href = self._get_href(item.uid)
        return self._put(href, item, None)

    def delete(self, href, etag):
        href = self._normalize_href(href)
        headers = self._default_headers()
        assert etag[0] == etag[-1] == '"'
        headers.update({
            'If-Match': etag
        })

        response = self._request(
            'DELETE',
            href,
            headers=headers
        )
        if response.status_code == 404:
            raise exceptions.NotFoundError(href)
        self._check_response(response)

    def _list(self, xml):
        response = self._request(
            'REPORT',
            '',
            data=xml,
            headers=self._default_headers()
        )
        response.raise_for_status()
        root = etree.XML(response.content)
        for element in root.iter('{DAV:}response'):
            etag = element.find('{DAV:}propstat').find(
                '{DAV:}prop').find('{DAV:}getetag').text
            href = self._normalize_href(element.find('{DAV:}href').text)
            yield href, etag


class CaldavStorage(DavStorage):

    fileext = '.ics'
    item_mimetype = 'text/calendar'
    dav_header = 'calendar-access'
    leif_class = 'CalDiscover'

    start_date = None
    end_date = None

    get_multi_template = '''<?xml version="1.0" encoding="utf-8" ?>
        <C:calendar-multiget xmlns:D="DAV:"
            xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <D:getetag/>
                <C:calendar-data/>
            </D:prop>
            {hrefs}
        </C:calendar-multiget>'''

    get_multi_data_query = '{urn:ietf:params:xml:ns:caldav}calendar-data'

    def __init__(self, start_date=None, end_date=None,
                 item_types=('VTODO', 'VEVENT'), **kwargs):
        '''
        :param start_date: Start date of timerange to show, default -inf.
        :param end_date: End date of timerange to show, default +inf.
        :param item_types: The item types to show from the server. Dependent on
            server functionality, no clientside validation of results. This
            currently only affects the `list` method, but this shouldn't cause
            problems in the normal usecase.
        '''
        super(CaldavStorage, self).__init__(**kwargs)
        if isinstance(item_types, str):
            item_types = [x.strip() for x in item_types.split(',')]
        self.item_types = tuple(item_types)
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

        self._list_template = self._get_list_template()

    def _get_list_template(self):
        data = '''<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:"
                xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <D:getetag/>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCALENDAR">
                        <C:comp-filter name="{component}">
                            {caldavfilter}
                        </C:comp-filter>
                    </C:comp-filter>
                </C:filter>
            </C:calendar-query>'''
        start = self.start_date
        end = self.end_date
        caldavfilter = ''
        if start is not None and end is not None:
            start = start.strftime(CALDAV_DT_FORMAT)
            end = end.strftime(CALDAV_DT_FORMAT)
            caldavfilter = ('<C:time-range start="{start}" end="{end}"/>'
                            .format(start=start, end=end))
        return data.format(caldavfilter=caldavfilter, component='{item_type}')

    def list(self):
        hrefs = set()
        for t in self.item_types:
            xml = self._list_template.format(item_type=t)
            for href, etag in self._list(xml):
                assert href not in hrefs
                hrefs.add(href)
                yield href, etag


class CarddavStorage(DavStorage):

    fileext = '.vcf'
    item_mimetype = 'text/vcard'
    dav_header = 'addressbook'
    leif_class = 'CardDiscover'

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

    def list(self):
        return self._list('''<?xml version="1.0" encoding="utf-8" ?>
            <C:addressbook-query xmlns:D="DAV:"
                    xmlns:C="urn:ietf:params:xml:ns:carddav">
                <D:prop>
                    <D:getetag/>
                </D:prop>
                <C:filter>
                    <C:comp-filter name="VCARD"/>
                </C:filter>
            </C:addressbook-query>''')
