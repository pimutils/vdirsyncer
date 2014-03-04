# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.dav.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer, Christian Geier and contributors
    :license: MIT, see LICENSE for more details.
'''

from ..base import Storage, Item
import vdirsyncer.exceptions as exceptions
import requests
import urlparse
from lxml import etree


class DavStorage(Storage):

    fileext = None
    item_mimetype = None
    dav_header = None
    get_multi_template = None
    get_multi_data_query = None
    list_xml = None

    _session = None
    _repr_attributes = ('url', 'username')

    def __init__(self, url, username='', password='', verify=True,
                 auth='basic', useragent='vdirsyncer', _request_func=None,
                 **kwargs):
        '''
        :param url: Direct URL for the CalDAV collection. No autodiscovery.
        :param username: Username for authentication.
        :param password: Password for authentication.
        :param verify: Verify SSL certificate, default True.
        :param auth: Authentication method, from {'basic', 'digest'}, default
                     'basic'.
        :param useragent: Default 'vdirsyncer'.
        :param _request_func: Function to use for network calls. Same API as
                              requests.request. Useful for tests.
        '''
        super(DavStorage, self).__init__(**kwargs)
        self._request = _request_func or self._request

        self._settings = {'verify': verify}
        if auth == 'basic':
            self._settings['auth'] = (username, password)
        elif auth == 'digest':
            from requests.auth import HTTPDigestAuth
            self._settings['auth'] = HTTPDigestAuth(username, password)
        else:
            raise ValueError('Unknown authentication method: {}'.format(auth))

        self.username, self.password = username, password
        self.useragent = useragent
        self.url = url.rstrip('/') + '/'
        self.parsed_url = urlparse.urlparse(self.url)

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

    def _simplify_href(self, href):
        '''Used to strip hrefs off the collection's URL, to leave only the
        filename.'''
        href = urlparse.urlparse(href).path
        if href.startswith('/'):
            return href
        assert '/' not in href
        return self.parsed_url.path + href

    def _get_href(self, uid):
        return self._simplify_href(super(DavStorage, self)._get_href(uid))

    def _default_headers(self):
        return {
            'User-Agent': self.useragent,
            'Content-Type': 'application/xml; charset=UTF-8'
        }

    def _request(self, method, path, data=None, headers=None):
        if self._session is None:
            self._session = requests.session()
        url = self.parsed_url.scheme + '://' + self.parsed_url.netloc + path
        return self._session.request(method, url, data=data, headers=headers,
                                     **self._settings)

    @staticmethod
    def _check_response(response):
        if response.status_code == 412:
            raise exceptions.PreconditionFailed()
        response.raise_for_status()

    def get(self, href):
        ((actual_href, obj, etag),) = self.get_multi([href])
        assert href == actual_href
        return obj, etag

    def get_multi(self, hrefs):
        if not hrefs:
            return ()
        hrefs = [self._simplify_href(href) for href in hrefs]

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
            href = self._simplify_href(
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

    def update(self, href, obj, etag):
        href = self._simplify_href(href)
        headers = self._default_headers()
        headers.update({
            'Content-Type': self.item_mimetype,
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

    def upload(self, obj):
        href = self._get_href(obj.uid)
        headers = self._default_headers()
        headers.update({
            'Content-Type': self.item_mimetype,
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

    def delete(self, href, etag):
        href = self._simplify_href(href)
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

    def list(self):
        response = self._request(
            'REPORT',
            '',
            data=self.list_xml,
            headers=self._default_headers()
        )
        response.raise_for_status()
        root = etree.XML(response.content)
        for element in root.iter('{DAV:}response'):
            etag = element.find('{DAV:}propstat').find(
                '{DAV:}prop').find('{DAV:}getetag').text
            href = self._simplify_href(element.find('{DAV:}href').text)
            yield href, etag
