# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.dav.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer, Christian Geier and contributors
    :license: MIT, see LICENSE for more details.
'''

from ..base import Storage
import vdirsyncer.exceptions as exceptions
import requests
import urlparse


class DavStorage(Storage):

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

    def _simplify_href(self, href):
        href = urlparse.urlparse(href).path
        if href.startswith(self.parsed_url.path):
            href = href[len(self.parsed_url.path):]
        assert '/' not in href, href
        return href

    def _request(self, method, item, data=None, headers=None):
        if self._session is None:
            self._session = requests.session()
        assert '/' not in item
        url = self.url + item
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
