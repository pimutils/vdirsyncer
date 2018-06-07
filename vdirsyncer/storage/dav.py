# -*- coding: utf-8 -*-

import datetime
import logging
import urllib.parse as urlparse
import xml.etree.ElementTree as etree

from inspect import getfullargspec

import requests
from requests.exceptions import HTTPError

from .base import Storage, normalize_meta_value
from ._rust import RustStorageMixin
from .. import exceptions, http, native, utils
from ..http import USERAGENT, prepare_auth, \
    prepare_client_cert, prepare_verify


dav_logger = logging.getLogger(__name__)

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'


def _generate_path_reserved_chars():
    for x in "/?#[]!$&'()*+,;":
        x = urlparse.quote(x, '')
        yield x.upper()
        yield x.lower()


_path_reserved_chars = frozenset(_generate_path_reserved_chars())
del _generate_path_reserved_chars


class InvalidXMLResponse(exceptions.InvalidResponse):
    pass


_BAD_XML_CHARS = (
    b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f'
    b'\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'
)


def _clean_body(content, bad_chars=_BAD_XML_CHARS):
    new_content = content.translate(None, bad_chars)
    if new_content != content:
        dav_logger.warning(
            'Your server incorrectly returned ASCII control characters in its '
            'XML. Vdirsyncer ignores those, but this is a bug in your server.'
        )
    return new_content


def _parse_xml(content):
    try:
        return etree.XML(_clean_body(content))
    except etree.ParseError as e:
        raise InvalidXMLResponse('Invalid XML encountered: {}\n'
                                 'Double-check the URLs in your config.'
                                 .format(e))


def _merge_xml(items):
    if not items:
        return None
    rv = items[0]
    for item in items[1:]:
        rv.extend(item.getiterator())
    return rv


class Discover(object):
    _namespace = None
    _resourcetype = None
    _homeset_xml = None
    _homeset_tag = None
    _well_known_uri = None
    _collection_xml = b"""<?xml version="1.0" encoding="utf-8" ?>
    <d:propfind xmlns:d="DAV:">
        <d:prop>
            <d:resourcetype />
        </d:prop>
    </d:propfind>
    """

    def __init__(self, session, kwargs):
        if kwargs.pop('collection', None) is not None:
            raise TypeError('collection argument must not be given.')

        self.session = session
        self.kwargs = kwargs

    @staticmethod
    def _get_collection_from_url(url):
        _, collection = url.rstrip('/').rsplit('/', 1)
        return urlparse.unquote(collection)

    def find_principal(self):
        try:
            return self._find_principal_impl('')
        except (HTTPError, exceptions.Error):
            dav_logger.debug('Trying out well-known URI')
            return self._find_principal_impl(self._well_known_uri)

    def _find_principal_impl(self, url):
        headers = self.session.get_default_headers()
        headers['Depth'] = '0'
        body = b"""
        <d:propfind xmlns:d="DAV:">
            <d:prop>
                <d:current-user-principal />
            </d:prop>
        </d:propfind>
        """

        response = self.session.request('PROPFIND', url, headers=headers,
                                        data=body)

        root = _parse_xml(response.content)
        rv = root.find('.//{DAV:}current-user-principal/{DAV:}href')
        if rv is None:
            # This is for servers that don't support current-user-principal
            # E.g. Synology NAS
            # See https://github.com/pimutils/vdirsyncer/issues/498
            dav_logger.debug(
                'No current-user-principal returned, re-using URL {}'
                .format(response.url))
            return response.url
        return urlparse.urljoin(response.url, rv.text).rstrip('/') + '/'

    def find_home(self):
        url = self.find_principal()
        headers = self.session.get_default_headers()
        headers['Depth'] = '0'
        response = self.session.request('PROPFIND', url,
                                        headers=headers,
                                        data=self._homeset_xml)

        root = etree.fromstring(response.content)
        # Better don't do string formatting here, because of XML namespaces
        rv = root.find('.//' + self._homeset_tag + '/{DAV:}href')
        if rv is None:
            raise InvalidXMLResponse('Couldn\'t find home-set.')
        return urlparse.urljoin(response.url, rv.text).rstrip('/') + '/'

    def find_collections(self):
        rv = None
        try:
            rv = list(self._find_collections_impl(''))
        except (HTTPError, exceptions.Error):
            pass

        if rv:
            return rv
        dav_logger.debug('Given URL is not a homeset URL')
        return self._find_collections_impl(self.find_home())

    def _check_collection_resource_type(self, response):
        if self._resourcetype is None:
            return True

        props = _merge_xml(response.findall(
            '{DAV:}propstat/{DAV:}prop'
        ))
        if props is None or not len(props):
            dav_logger.debug('Skipping, missing <prop>: %s', response)
            return False
        if props.find('{DAV:}resourcetype/' + self._resourcetype) \
           is None:
            dav_logger.debug('Skipping, not of resource type %s: %s',
                             self._resourcetype, response)
            return False
        return True

    def _find_collections_impl(self, url):
        headers = self.session.get_default_headers()
        headers['Depth'] = '1'
        r = self.session.request('PROPFIND', url, headers=headers,
                                 data=self._collection_xml)
        root = _parse_xml(r.content)
        done = set()
        for response in root.findall('{DAV:}response'):
            if not self._check_collection_resource_type(response):
                continue

            href = response.find('{DAV:}href')
            if href is None:
                raise InvalidXMLResponse('Missing href tag for collection '
                                         'props.')
            href = urlparse.urljoin(r.url, href.text)
            if href not in done:
                done.add(href)
                yield {'href': href}

    def discover(self):
        for c in self.find_collections():
            url = c['href']
            collection = self._get_collection_from_url(url)
            storage_args = dict(self.kwargs)
            storage_args.update({'url': url, 'collection': collection})
            yield storage_args

    def create(self, collection):
        if collection is None:
            collection = self._get_collection_from_url(self.kwargs['url'])

        for c in self.discover():
            if c['collection'] == collection:
                return c

        home = self.find_home()
        url = urlparse.urljoin(
            home,
            urlparse.quote(collection, '/@')
        )

        try:
            url = self._create_collection_impl(url)
        except HTTPError as e:
            raise NotImplementedError(e)
        else:
            rv = dict(self.kwargs)
            rv['collection'] = collection
            rv['url'] = url
            return rv

    def _create_collection_impl(self, url):
        data = '''<?xml version="1.0" encoding="utf-8" ?>
            <D:mkcol xmlns:D="DAV:">
                <D:set>
                    <D:prop>
                        <D:resourcetype>
                            <D:collection/>
                            {}
                        </D:resourcetype>
                    </D:prop>
                </D:set>
            </D:mkcol>
        '''.format(
            etree.tostring(etree.Element(self._resourcetype),
                           encoding='unicode')
        ).encode('utf-8')

        response = self.session.request(
            'MKCOL',
            url,
            data=data,
            headers=self.session.get_default_headers(),
        )
        return response.url


class CalDiscover(Discover):
    _namespace = 'urn:ietf:params:xml:ns:caldav'
    _resourcetype = '{%s}calendar' % _namespace
    _homeset_xml = b"""
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
        <d:prop>
            <c:calendar-home-set />
        </d:prop>
    </d:propfind>
    """
    _homeset_tag = '{%s}calendar-home-set' % _namespace
    _well_known_uri = '/.well-known/caldav'


class CardDiscover(Discover):
    _namespace = 'urn:ietf:params:xml:ns:carddav'
    _resourcetype = '{%s}addressbook' % _namespace
    _homeset_xml = b"""
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">
        <d:prop>
            <c:addressbook-home-set />
        </d:prop>
    </d:propfind>
    """
    _homeset_tag = '{%s}addressbook-home-set' % _namespace
    _well_known_uri = '/.well-known/carddav'


class DAVSession(object):
    '''
    A helper class to connect to DAV servers.
    '''

    @classmethod
    def init_and_remaining_args(cls, **kwargs):
        argspec = getfullargspec(cls.__init__)
        self_args, remainder = \
            utils.split_dict(kwargs, argspec.args.__contains__)

        return cls(**self_args), remainder

    def __init__(self, url, username='', password='', verify=True, auth=None,
                 useragent=USERAGENT, verify_fingerprint=None,
                 auth_cert=None):
        self._settings = {
            'cert': prepare_client_cert(auth_cert),
            'auth': prepare_auth(auth, username, password)
        }
        self._settings.update(prepare_verify(verify, verify_fingerprint))

        self.useragent = useragent
        self.url = url.rstrip('/') + '/'

        self._session = requests.session()

    def request(self, method, path, **kwargs):
        url = self.url
        if path:
            url = urlparse.urljoin(self.url, path)

        more = dict(self._settings)
        more.update(kwargs)
        return http.request(method, url, session=self._session, **more)

    def get_default_headers(self):
        return {
            'User-Agent': self.useragent,
            'Content-Type': 'application/xml; charset=UTF-8'
        }


class DAVStorage(RustStorageMixin, Storage):
    # the file extension of items. Useful for testing against radicale.
    fileext = None
    # mimetype of items
    item_mimetype = None
    # XML to use when fetching multiple hrefs.
    get_multi_template = None
    # The LXML query for extracting results in get_multi
    get_multi_data_query = None
    # The Discover subclass to use
    discovery_class = None
    # The DAVSession class to use
    session_class = DAVSession

    _repr_attributes = ('username', 'url')

    _property_table = {
        'displayname': ('displayname', 'DAV:'),
    }

    def __init__(self, **kwargs):
        # defined for _repr_attributes
        self.username = kwargs.get('username')
        self.url = kwargs.get('url')

        self.session, kwargs = \
            self.session_class.init_and_remaining_args(**kwargs)
        super(DAVStorage, self).__init__(**kwargs)

    import inspect
    __init__.__signature__ = inspect.signature(session_class.__init__)

    @classmethod
    def discover(cls, **kwargs):
        session, _ = cls.session_class.init_and_remaining_args(**kwargs)
        d = cls.discovery_class(session, kwargs)
        return d.discover()

    @classmethod
    def create_collection(cls, collection, **kwargs):
        session, _ = cls.session_class.init_and_remaining_args(**kwargs)
        d = cls.discovery_class(session, kwargs)
        return d.create(collection)

    def get_meta(self, key):
        try:
            tagname, namespace = self._property_table[key]
        except KeyError:
            raise exceptions.UnsupportedMetadataError()

        xpath = '{%s}%s' % (namespace, tagname)
        data = '''<?xml version="1.0" encoding="utf-8" ?>
            <D:propfind xmlns:D="DAV:">
                <D:prop>
                    {}
                </D:prop>
            </D:propfind>
        '''.format(
            etree.tostring(etree.Element(xpath), encoding='unicode')
        ).encode('utf-8')

        headers = self.session.get_default_headers()
        headers['Depth'] = '0'

        response = self.session.request(
            'PROPFIND', '',
            data=data, headers=headers
        )

        root = _parse_xml(response.content)

        for prop in root.findall('.//' + xpath):
            text = normalize_meta_value(getattr(prop, 'text', None))
            if text:
                return text
        return u''

    def set_meta(self, key, value):
        try:
            tagname, namespace = self._property_table[key]
        except KeyError:
            raise exceptions.UnsupportedMetadataError()

        lxml_selector = '{%s}%s' % (namespace, tagname)
        element = etree.Element(lxml_selector)
        element.text = normalize_meta_value(value)

        data = '''<?xml version="1.0" encoding="utf-8" ?>
            <D:propertyupdate xmlns:D="DAV:">
                <D:set>
                    <D:prop>
                        {}
                    </D:prop>
                </D:set>
            </D:propertyupdate>
        '''.format(etree.tostring(element, encoding='unicode')).encode('utf-8')

        self.session.request(
            'PROPPATCH', '',
            data=data, headers=self.session.get_default_headers()
        )

        # XXX: Response content is currently ignored. Though exceptions are
        # raised for HTTP errors, a multistatus with errorcodes inside is not
        # parsed yet. Not sure how common those are, or how they look like. It
        # might be easier (and safer in case of a stupid server) to just issue
        # a PROPFIND to see if the value got actually set.


class CalDAVStorage(DAVStorage):
    storage_name = 'caldav'
    fileext = '.ics'
    item_mimetype = 'text/calendar'
    discovery_class = CalDiscover

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

    _property_table = dict(DAVStorage._property_table)
    _property_table.update({
        'color': ('calendar-color', 'http://apple.com/ns/ical/'),
    })

    def __init__(self, start_date=None, end_date=None,
                 item_types=(), **kwargs):
        super(CalDAVStorage, self).__init__(**kwargs)
        if not isinstance(item_types, (list, tuple)):
            raise exceptions.UserError('item_types must be a list.')

        self.item_types = tuple(x.upper() for x in item_types)
        if (start_date is None) != (end_date is None):
            raise exceptions.UserError('If start_date is given, '
                                       'end_date has to be given too.')
        elif start_date is not None and end_date is not None:
            namespace = dict(datetime.__dict__)
            namespace['start_date'] = self.start_date = \
                (eval(start_date, namespace)
                 if isinstance(start_date, (bytes, str))
                 else start_date)
            self.end_date = \
                (eval(end_date, namespace)
                 if isinstance(end_date, (bytes, str))
                 else end_date)

        self._native_storage = native.ffi.gc(
            native.lib.vdirsyncer_init_caldav(
                kwargs['url'].encode('utf-8'),
                kwargs.get('username', '').encode('utf-8'),
                kwargs.get('password', '').encode('utf-8'),
                kwargs.get('useragent', '').encode('utf-8'),
                kwargs.get('verify_cert', '').encode('utf-8'),
                kwargs.get('auth_cert', '').encode('utf-8'),
                int(self.start_date.timestamp()) if self.start_date else -1,
                int(self.end_date.timestamp()) if self.end_date else -1,
                'VEVENT' in item_types,
                'VJOURNAL' in item_types,
                'VTODO' in item_types
            ),
            native.lib.vdirsyncer_storage_free
        )


class CardDAVStorage(DAVStorage):
    storage_name = 'carddav'
    fileext = '.vcf'
    item_mimetype = 'text/vcard'
    discovery_class = CardDiscover

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

    def __init__(self, **kwargs):
        self._native_storage = native.ffi.gc(
            native.lib.vdirsyncer_init_carddav(
                kwargs['url'].encode('utf-8'),
                kwargs.get('username', '').encode('utf-8'),
                kwargs.get('password', '').encode('utf-8'),
                kwargs.get('useragent', '').encode('utf-8'),
                kwargs.get('verify_cert', '').encode('utf-8'),
                kwargs.get('auth_cert', '').encode('utf-8')
            ),
            native.lib.vdirsyncer_storage_free
        )

        super(CardDAVStorage, self).__init__(**kwargs)
