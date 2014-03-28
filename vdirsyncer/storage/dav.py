# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.dav
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer, Christian Geier and contributors
    :license: MIT, see LICENSE for more details.
'''

from .base import Item
from .http import HttpStorageBase
import vdirsyncer.exceptions as exceptions
import vdirsyncer.log as log
import requests
import datetime
import urlparse
from lxml import etree


dav_logger = log.get('storage.dav')

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'
CONFIG_DT_FORMAT = '%Y-%m-%d'


class DavStorage(HttpStorageBase):

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
    _repr_attributes = ('url', 'username')

    def __init__(self, **kwargs):
        super(DavStorage, self).__init__(**kwargs)

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
            collection = c['href']
            if collection.startswith(url):
                collection = collection[len(url):]
            s = cls(url=url, collection=collection, **kwargs)
            s.displayname = c['displayname']
            yield s

    def _normalize_href(self, href):
        '''Normalize the href to be a path only relative to hostname and
        schema.'''
        href = urlparse.urlparse(href).path
        if href.startswith('/'):
            return href
        assert '/' not in href
        return self.parsed_url.path + href

    def _get_href(self, uid):
        return self._normalize_href(super(DavStorage, self)._get_href(uid))

    def _request(self, method, path, data=None, headers=None):
        path = path or self.parsed_url.path
        assert path.startswith(self.parsed_url.path)
        if self._session is None:
            self._session = requests.session()
        url = self.parsed_url.scheme + '://' + self.parsed_url.netloc + path
        dav_logger.debug(u'Method: {}'.format(method))
        dav_logger.debug(u'Path: {}'.format(path))
        dav_logger.debug(u'Headers: {}'.format(headers))
        dav_logger.debug(u'/// DATA')
        dav_logger.debug(data)
        dav_logger.debug(u'/// END DATA')
        r = self._session.request(method, url, data=data, headers=headers,
                                  **self._settings)
        dav_logger.debug(r.status_code)
        dav_logger.debug(r.text)
        return r

    @staticmethod
    def _check_response(response):
        if response.status_code == 412:
            raise exceptions.PreconditionFailed(response.reason)
        response.raise_for_status()

    def get(self, href):
        ((actual_href, obj, etag),) = self.get_multi([href])
        assert href == actual_href
        return obj, etag

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
            obj = element \
                .find('{DAV:}propstat') \
                .find('{DAV:}prop') \
                .find(self.get_multi_data_query).text
            etag = element \
                .find('{DAV:}propstat') \
                .find('{DAV:}prop') \
                .find('{DAV:}getetag').text
            if isinstance(obj, bytes):
                obj = obj.decode(response.encoding)
            if isinstance(etag, bytes):
                etag = etag.decode(response.encoding)
            rv.append((href, Item(obj), etag))
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

    def _put(self, href, obj, etag):
        headers = self._default_headers()
        headers['Content-Type'] = self.item_mimetype,
        if etag is None:
            headers['If-None-Match'] = '*'
        else:
            assert etag[0] == etag[-1] == '"'
            headers['If-Match'] = etag

        response = self._request(
            'PUT',
            href,
            data=obj.raw.encode('utf-8'),
            headers=headers
        )
        self._check_response(response)
        etag = response.headers.get('etag', None)
        if not etag:
            obj2, etag = self.get(href)
            assert obj2.uid == obj.uid
        return href, etag

    def update(self, href, obj, etag):
        href = self._normalize_href(href)
        if etag is None:
            raise ValueError('etag must be given and must not be None.')
        return self._put(href, obj, etag)

    def upload(self, obj):
        href = self._get_href(obj.uid)
        return self._put(href, obj, None)

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
