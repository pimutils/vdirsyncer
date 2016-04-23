# -*- coding: utf-8 -*-

import datetime
import logging

import xml.etree.ElementTree as etree

import requests
from requests.exceptions import HTTPError

from .base import Item, Storage, normalize_meta_value
from .http import HTTP_STORAGE_PARAMETERS, USERAGENT, prepare_auth, \
    prepare_client_cert, prepare_verify
from .. import exceptions, utils
from ..utils.compat import PY2, getargspec_ish, text_type, to_native


dav_logger = logging.getLogger(__name__)

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'

_path_reserved_chars = frozenset(utils.compat.urlquote(x, '')
                                 for x in "/?#[]!$&'()*+,;=")


def _contains_quoted_reserved_chars(x):
    for y in _path_reserved_chars:
        if y in x:
            dav_logger.debug('Unsafe character: {!r}'.format(y))
            return True
    return False


def _normalize_href(base, href):
    '''Normalize the href to be a path only relative to hostname and
    schema.'''
    orig_href = href
    base = to_native(base, 'utf-8')
    href = to_native(href, 'utf-8')
    if not href:
        raise ValueError(href)

    x = utils.compat.urlparse.urljoin(base, href)
    x = utils.compat.urlparse.urlsplit(x).path

    # Encoding issues:
    # - https://github.com/owncloud/contacts/issues/581
    # - https://github.com/Kozea/Radicale/issues/298
    old_x = None
    while old_x is None or x != old_x:
        if _contains_quoted_reserved_chars(x):
            break
        old_x = x
        x = utils.compat.urlunquote(x)

    x = utils.compat.urlquote(x, '/@%:')

    if orig_href == x:
        dav_logger.debug('Already normalized: {!r}'.format(x))
    else:
        dav_logger.debug('Normalized URL from {!r} to {!r}'
                         .format(orig_href, x))

    return x


class InvalidXMLResponse(exceptions.InvalidResponse):
    pass


def _parse_xml(content):
    try:
        return etree.XML(content)
    except etree.ParseError as e:
        raise InvalidXMLResponse('Invalid XML encountered: {}\n'
                                 'Double-check the URLs in your config.'
                                 .format(e))


def _merge_xml(items):
    rv = items[0]
    rv.extend(items[1:])
    return rv


def _fuzzy_matches_mimetype(strict, weak):
    # different servers give different getcontenttypes:
    # "text/vcard", "text/x-vcard", "text/x-vcard; charset=utf-8",
    # "text/directory;profile=vCard", "text/directory",
    # "text/vcard; charset=utf-8"
    if strict is None or weak is None:
        return True

    mediatype, subtype = strict.split('/')
    if subtype in weak:
        return True
    return False


class Discover(object):
    _namespace = None
    _resourcetype = None
    _homeset_xml = None
    _homeset_tag = None
    _well_known_uri = None
    _collection_xml = """
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
        return utils.compat.urlunquote(collection)

    def find_dav(self):
        try:
            response = self.session.request(
                'GET', self._well_known_uri, allow_redirects=False,
                headers=self.session.get_default_headers()
            )
            return response.headers.get('Location', '')
        except (HTTPError, exceptions.Error):
            # The user might not have well-known URLs set up and instead points
            # vdirsyncer directly to the DAV server.
            dav_logger.debug('Server does not support well-known URIs.')
            return ''

    def find_principal(self, url=None):
        if url is None:
            try:
                return self.find_principal('')
            except (HTTPError, exceptions.Error):
                return self.find_principal(self.find_dav())

        headers = self.session.get_default_headers()
        headers['Depth'] = 0
        body = """
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
            raise InvalidXMLResponse()
        return utils.compat.urlparse.urljoin(response.url, rv.text)

    def find_home(self, url=None):
        if url is None:
            url = self.find_principal()
        headers = self.session.get_default_headers()
        headers['Depth'] = 0
        response = self.session.request('PROPFIND', url,
                                        headers=headers,
                                        data=self._homeset_xml)

        root = etree.fromstring(response.content)
        # Better don't do string formatting here, because of XML namespaces
        rv = root.find('.//' + self._homeset_tag + '/{DAV:}href')
        if rv is None:
            raise InvalidXMLResponse()
        return utils.compat.urlparse.urljoin(response.url, rv.text)

    def find_collections(self, url=None):
        if url is None:
            url = self.find_home()
        headers = self.session.get_default_headers()
        headers['Depth'] = 1
        r = self.session.request('PROPFIND', url, headers=headers,
                                 data=self._collection_xml)
        root = _parse_xml(r.content)
        done = set()
        for response in root.findall('{DAV:}response'):
            props = _merge_xml(response.findall('{DAV:}propstat/{DAV:}prop'))
            if props.find('{DAV:}resourcetype/' + self._resourcetype) is None:
                continue

            href = response.find('{DAV:}href')
            if href is None:
                raise InvalidXMLResponse()
            href = utils.compat.urlparse.urljoin(r.url, href.text)
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
        url = utils.compat.urlparse.urljoin(
            home,
            utils.compat.urlquote(collection, '/@')
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
            to_native(etree.tostring(etree.Element(self._resourcetype)))
        )

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
    _homeset_xml = """
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
        <d:prop>
            <c:calendar-home-set />
        </d:prop>
    </d:propfind>
    """
    _homeset_tag = '{%s}calendar-home-set' % _namespace
    _well_known_uri = '/.well-known/caldav/'


class CardDiscover(Discover):
    _namespace = 'urn:ietf:params:xml:ns:carddav'
    _resourcetype = '{%s}addressbook' % _namespace
    _homeset_xml = """
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">
        <d:prop>
            <c:addressbook-home-set />
        </d:prop>
    </d:propfind>
    """
    _homeset_tag = '{%s}addressbook-home-set' % _namespace
    _well_known_uri = '/.well-known/carddav/'


class DavSession(object):
    '''
    A helper class to connect to DAV servers.
    '''

    @classmethod
    def init_and_remaining_args(cls, **kwargs):
        argspec = getargspec_ish(cls.__init__)
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

    @utils.cached_property
    def parsed_url(self):
        return utils.compat.urlparse.urlparse(self.url)

    def request(self, method, path, **kwargs):
        url = self.url
        if path:
            url = utils.compat.urlparse.urljoin(self.url, path)

        more = dict(self._settings)
        more.update(kwargs)
        return utils.http.request(method, url, session=self._session, **more)

    def get_default_headers(self):
        return {
            'User-Agent': self.useragent,
            'Content-Type': 'application/xml; charset=UTF-8'
        }


class DavStorage(Storage):

    __doc__ = '''
    :param url: Base URL or an URL to a collection.
    ''' + HTTP_STORAGE_PARAMETERS + '''

    .. note::

        Please also see :ref:`supported-servers`, as some servers may not work
        well.
    '''

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
    # The DavSession class to use
    session_class = DavSession

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
        super(DavStorage, self).__init__(**kwargs)

    if not PY2:
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

    def _normalize_href(self, *args, **kwargs):
        return _normalize_href(self.session.url, *args, **kwargs)

    def _get_href(self, item):
        href = utils.generate_href(item.ident)
        return self._normalize_href(href + self.fileext)

    def _is_item_mimetype(self, mimetype):
        return _fuzzy_matches_mimetype(self.item_mimetype, mimetype)

    def get(self, href):
        ((actual_href, item, etag),) = self.get_multi([href])
        assert href == actual_href
        return item, etag

    def get_multi(self, hrefs):
        hrefs = set(hrefs)
        href_xml = []
        for href in hrefs:
            if href != self._normalize_href(href):
                raise exceptions.NotFoundError(href)
            href_xml.append('<D:href>{}</D:href>'.format(href))
        if not href_xml:
            return ()

        data = self.get_multi_template.format(hrefs='\n'.join(href_xml))
        response = self.session.request(
            'REPORT',
            '',
            data=data,
            headers=self.session.get_default_headers()
        )
        root = _parse_xml(response.content)  # etree only can handle bytes
        rv = []
        hrefs_left = set(hrefs)
        for href, etag, prop in self._parse_prop_responses(root):
            raw = prop.find(self.get_multi_data_query)
            if raw is None:
                dav_logger.warning('Skipping {}, the item content is missing.'
                                   .format(href))
                continue

            raw = raw.text or u''

            if isinstance(raw, bytes):
                raw = raw.decode(response.encoding)
            if isinstance(etag, bytes):
                etag = etag.decode(response.encoding)

            try:
                hrefs_left.remove(href)
            except KeyError:
                if href in hrefs:
                    dav_logger.warning('Server sent item twice: {}'
                                       .format(href))
                else:
                    dav_logger.warning('Server sent unsolicited item: {}'
                                       .format(href))
            else:
                rv.append((href, Item(raw), etag))
        for href in hrefs_left:
            raise exceptions.NotFoundError(href)
        return rv

    def _put(self, href, item, etag):
        headers = self.session.get_default_headers()
        headers['Content-Type'] = self.item_mimetype
        if etag is None:
            headers['If-None-Match'] = '*'
        else:
            headers['If-Match'] = etag

        response = self.session.request(
            'PUT',
            href,
            data=item.raw.encode('utf-8'),
            headers=headers
        )
        etag = response.headers.get('etag', None)
        href = self._normalize_href(response.url)
        if not etag:
            # The server violated the RFC and didn't send an etag. This is
            # technically a race-condition, but too many popular servers do it.
            #
            # ownCloud: https://github.com/owncloud/contacts/issues/920
            dav_logger.debug('Server did not send etag, fetching {!r}'
                             .format(href))
            item2, etag = self.get(href)
        return href, etag

    def update(self, href, item, etag):
        if etag is None:
            raise ValueError('etag must be given and must not be None.')
        href, etag = self._put(self._normalize_href(href), item, etag)
        return etag

    def upload(self, item):
        href = self._get_href(item)
        return self._put(href, item, None)

    def delete(self, href, etag):
        href = self._normalize_href(href)
        headers = self.session.get_default_headers()
        headers.update({
            'If-Match': etag
        })

        self.session.request(
            'DELETE',
            href,
            headers=headers
        )

    def _parse_prop_responses(self, root):
        hrefs = set()
        for response in root.iter('{DAV:}response'):
            href = response.find('{DAV:}href')
            if href is None:
                dav_logger.error('Skipping response, href is missing.')
                continue

            href = self._normalize_href(href.text)

            if href in hrefs:
                # Servers that send duplicate hrefs:
                # - Zimbra
                #   https://github.com/pimutils/vdirsyncer/issues/88
                # - Davmail
                #   https://github.com/pimutils/vdirsyncer/issues/144
                dav_logger.warning('Skipping identical href: {!r}'
                                   .format(href))
                continue

            props = response.findall('{DAV:}propstat/{DAV:}prop')
            if not props:
                dav_logger.warning('Skipping {!r}, properties are missing.'
                                   .format(href))
                continue
            else:
                props = _merge_xml(props)

            if props.find('{DAV:}resourcetype/{DAV:}collection') is not None:
                dav_logger.debug('Skipping {!r}, is collection.'.format(href))
                continue

            etag = getattr(props.find('{DAV:}getetag'), 'text', '')
            if not etag:
                dav_logger.warning('Skipping {!r}, etag property is missing.'
                                   .format(href))

            contenttype = getattr(props.find('{DAV:}getcontenttype'),
                                  'text', None)
            if not self._is_item_mimetype(contenttype):
                dav_logger.debug('Skipping {!r}, {!r} != {!r}.'
                                 .format(href, contenttype,
                                         self.item_mimetype))
                continue

            hrefs.add(href)
            yield href, etag, props

    def list(self):
        headers = self.session.get_default_headers()
        headers['Depth'] = 1

        data = '''<?xml version="1.0" encoding="utf-8" ?>
            <D:propfind xmlns:D="DAV:">
                <D:prop>
                    <D:resourcetype/>
                    <D:getcontenttype/>
                    <D:getetag/>
                </D:prop>
            </D:propfind>
            '''

        # We use a PROPFIND request instead of addressbook-query due to issues
        # with Zimbra. See https://github.com/pimutils/vdirsyncer/issues/83
        response = self.session.request('PROPFIND', '', data=data,
                                        headers=headers)
        root = _parse_xml(response.content)

        rv = self._parse_prop_responses(root)
        for href, etag, prop in rv:
            yield href, etag

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
            to_native(etree.tostring(etree.Element(xpath)))
        )

        headers = self.session.get_default_headers()
        headers['Depth'] = 0

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
        '''.format(to_native(etree.tostring(element)))

        self.session.request(
            'PROPPATCH', '',
            data=data, headers=self.session.get_default_headers()
        )

        # XXX: Response content is currently ignored. Though exceptions are
        # raised for HTTP errors, a multistatus with errorcodes inside is not
        # parsed yet. Not sure how common those are, or how they look like. It
        # might be easier (and safer in case of a stupid server) to just issue
        # a PROPFIND to see if the value got actually set.


class CaldavStorage(DavStorage):

    __doc__ = '''
    CalDAV.

    You can set a timerange to synchronize with the parameters ``start_date``
    and ``end_date``. Inside those parameters, you can use any Python
    expression to return a valid :py:class:`datetime.datetime` object. For
    example, the following would synchronize the timerange from one year in the
    past to one year in the future::

        start_date = datetime.now() - timedelta(days=365)
        end_date = datetime.now() + timedelta(days=365)

    Either both or none have to be specified. The default is to synchronize
    everything.

    You can set ``item_types`` to restrict the *kind of items* you want to
    synchronize. For example, if you want to only synchronize events (but don't
    download any tasks from the server), set ``item_types = ["VEVENT"]``. If
    you want to synchronize events and tasks, but have some ``VJOURNAL`` items
    on the server you don't want to synchronize, use ``item_types = ["VEVENT",
    "VTODO"]``.

    :param start_date: Start date of timerange to show, default -inf.
    :param end_date: End date of timerange to show, default +inf.
    :param item_types: Kind of items to show. The default, the empty list, is
        to show all. This depends on particular features on the server, the
        results are not validated.
    ''' + DavStorage.__doc__

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

    _property_table = dict(DavStorage._property_table)
    _property_table.update({
        'color': ('calendar-color', 'http://apple.com/ns/ical/'),
    })

    def __init__(self, start_date=None, end_date=None,
                 item_types=(), **kwargs):
        super(CaldavStorage, self).__init__(**kwargs)
        if not isinstance(item_types, (list, tuple)):
            raise exceptions.UserError('item_types must be a list.')

        self.item_types = tuple(item_types)
        if (start_date is None) != (end_date is None):
            raise exceptions.UserError('If start_date is given, '
                                       'end_date has to be given too.')
        elif start_date is not None and end_date is not None:
            namespace = dict(datetime.__dict__)
            namespace['start_date'] = self.start_date = \
                (eval(start_date, namespace)
                 if isinstance(start_date, (bytes, text_type))
                 else start_date)
            self.end_date = \
                (eval(end_date, namespace)
                 if isinstance(end_date, (bytes, text_type))
                 else end_date)

    @staticmethod
    def _get_list_filters(components, start, end):
        if components:
            caldavfilter = '''
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="{component}">
                        {timefilter}
                    </C:comp-filter>
                </C:comp-filter>
                '''

            if start is not None and end is not None:
                start = start.strftime(CALDAV_DT_FORMAT)
                end = end.strftime(CALDAV_DT_FORMAT)

                timefilter = ('<C:time-range start="{start}" end="{end}"/>'
                              .format(start=start, end=end))
            else:
                timefilter = ''

            for component in components:
                yield caldavfilter.format(component=component,
                                          timefilter=timefilter)
        else:
            if start is not None and end is not None:
                for x in CaldavStorage._get_list_filters(('VTODO', 'VEVENT'),
                                                         start, end):
                    yield x

    def list(self):
        caldavfilters = list(self._get_list_filters(
            self.item_types,
            self.start_date,
            self.end_date
        ))
        if not caldavfilters:
            # If we don't have any filters (which is the default), taking the
            # risk of sending a calendar-query is not necessary. There doesn't
            # seem to be a widely-usable way to send calendar-queries with the
            # same semantics as a PROPFIND request... so why not use PROPFIND
            # instead?
            #
            # See https://github.com/dmfs/tasks/issues/118 for backstory.
            for x in DavStorage.list(self):
                yield x

        data = '''<?xml version="1.0" encoding="utf-8" ?>
            <C:calendar-query xmlns:D="DAV:"
                xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <D:getcontenttype/>
                    <D:getetag/>
                </D:prop>
                <C:filter>
                {caldavfilter}
                </C:filter>
            </C:calendar-query>'''

        headers = self.session.get_default_headers()
        # https://github.com/pimutils/vdirsyncer/issues/166
        # The default in CalDAV's calendar-queries is 0, but the examples use
        # an explicit value of 1 for querying items. it is extremely unclear in
        # the spec which values from WebDAV are actually allowed.
        headers['Depth'] = 1

        for caldavfilter in caldavfilters:
            xml = data.format(caldavfilter=caldavfilter)
            response = self.session.request('REPORT', '', data=xml,
                                            headers=headers)
            root = _parse_xml(response.content)
            rv = self._parse_prop_responses(root)
            for href, etag, prop in rv:
                yield href, etag


class CarddavStorage(DavStorage):

    __doc__ = '''
    CardDAV.
    ''' + DavStorage.__doc__

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
