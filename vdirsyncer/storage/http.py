# -*- coding: utf-8 -*-

from .base import Item, Storage
from ..exceptions import NotFoundError
from ..utils import expand_path, get_password, request
from ..utils.compat import iteritems, text_type, urlparse
from ..utils.vobject import split_collection

USERAGENT = 'vdirsyncer'


def prepare_auth(auth, username, password):
    if username and password:
        if auth == 'basic':
            return (username, password)
        elif auth == 'digest':
            from requests.auth import HTTPDigestAuth
            return HTTPDigestAuth(username, password)
        elif auth == 'guess' or auth is None:
            import requests_toolbelt
            if not hasattr(requests_toolbelt, 'GuessAuth'):
                raise RuntimeError('Your version of requests_toolbelt is too '
                                   'old.')
            return requests_toolbelt.GuessAuth(username, password)
        else:
            raise ValueError('Unknown authentication method: {}'.format(auth))
    elif auth:
        raise ValueError('For {} authentication, you need to specify username '
                         'and password.'.format(auth))
    else:
        return None


def prepare_verify(verify):
    if isinstance(verify, (text_type, bytes)):
        return expand_path(verify)
    return verify


def prepare_client_cert(cert):
    if isinstance(cert, (text_type, bytes)):
        cert = expand_path(cert)
    elif isinstance(cert, list):
        cert = tuple(map(prepare_client_cert, cert))
    return cert


HTTP_STORAGE_PARAMETERS = '''
    :param username: Username for authentication.
    :param password: Password for authentication.
    :param verify: Verify SSL certificate, default True. This can also be a
        local path to a self-signed SSL certificate. See :ref:`ssl-tutorial`
        for more information.
    :param verify_fingerprint: Optional. SHA1 or MD5 fingerprint of the
        expected server certificate. See :ref:`ssl-tutorial` for more
        information.
    :param auth: Optional. Either ``basic``, ``digest`` or ``guess``. Default
        ``guess``. If you know yours, consider setting it explicitly for
        performance.
    :param auth_cert: Optional. Either a path to a certificate with a client
        certificate and the key or a list of paths to the files with them.
    :param useragent: Default ``vdirsyncer``.
'''


class HttpStorage(Storage):
    __doc__ = '''
    Use a simple ``.ics`` file (or similar) from the web.

    :param url: URL to the ``.ics`` file.
    ''' + HTTP_STORAGE_PARAMETERS + '''

    A simple example::

        [pair holidays]
        a = holidays_local
        b = holidays_remote

        [storage holidays_local]
        type = filesystem
        path = ~/.config/vdir/calendars/holidays/
        fileext = .ics

        [storage holidays_remote]
        type = http
        url = https://example.com/holidays_from_hicksville.ics
    '''

    storage_name = 'http'
    read_only = True
    _repr_attributes = ('username', 'url')
    _items = None

    def __init__(self, url, username='', password='', verify=True, auth=None,
                 useragent=USERAGENT, verify_fingerprint=None, auth_cert=None,
                 **kwargs):
        super(HttpStorage, self).__init__(**kwargs)

        if username and not password:
            password = get_password(username, url)

        self._settings = {
            'verify': prepare_verify(verify),
            'verify_fingerprint': verify_fingerprint,
            'auth': prepare_auth(auth, username, password),
            'cert': prepare_client_cert(auth_cert),
            'latin1_fallback': False,
        }
        self.username, self.password = username, password
        self.useragent = useragent

        collection = kwargs.get('collection')
        if collection is not None:
            url = urlparse.urljoin(url, collection)
        self.url = url
        self.parsed_url = urlparse.urlparse(self.url)

    def _default_headers(self):
        return {'User-Agent': self.useragent}

    def list(self):
        r = request('GET', self.url, headers=self._default_headers(),
                    **self._settings)
        self._items = {}

        for item in split_collection(r.text):
            item = Item(item)
            etag = item.hash
            self._items[item.ident] = item, etag

        return ((href, etag) for href, (item, etag) in iteritems(self._items))

    def get(self, href):
        if self._items is None:
            self.list()

        try:
            return self._items[href]
        except KeyError:
            raise NotFoundError(href)
