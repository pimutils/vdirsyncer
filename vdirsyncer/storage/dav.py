# -*- coding: utf-8 -*-

import datetime

from lxml import etree

from requests import session as requests_session
from requests.exceptions import HTTPError

from .base import Item, Storage
from .http import HTTP_STORAGE_PARAMETERS, USERAGENT, prepare_auth, \
    prepare_client_cert, prepare_verify
from .. import exceptions, log, utils
from ..utils.compat import text_type


dav_logger = log.get(__name__)

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'


def _normalize_href(base, href):
    '''Normalize the href to be a path only relative to hostname and
    schema.'''
    if not href:
        raise ValueError(href)
    x = utils.urlparse.urljoin(base, href)
    x = utils.urlparse.urlsplit(x).path
    return x


def _encode_href(x):
    return utils.compat.urlquote(x, '/@')


def _decode_href(x):
    return utils.compat.urlunquote(x)


class InvalidXMLResponse(exceptions.InvalidResponse):
    pass


def _parse_xml(content):
    try:
        return etree.XML(content)
    except etree.Error as e:
        raise InvalidXMLResponse('Invalid XML encountered: {0}\n'
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


def _get_collection_from_url(url):
    _, collection = url.rstrip('/').rsplit('/', 1)
    return collection


class Discover(object):
    _resourcetype = None
    _homeset_xml = None
    _homeset_tag = None
    _well_known_uri = None
    _collection_xml = """
    <d:propfind xmlns:d="DAV:">
        <d:prop>
            <d:resourcetype />
            <d:displayname />
        </d:prop>
    </d:propfind>
    """

    def __init__(self, session):
        self.session = session

    def find_dav(self):
        try:
            response = self.session.request('GET', self._well_known_uri,
                                            allow_redirects=False)
            return response.headers.get('Location', '')
        except (HTTPError, exceptions.Error):
            # The user might not have well-known URLs set up and instead points
            # vdirsyncer directly to the DAV server.
            dav_logger.debug('Server does not support well-known URIs.')
            return ''

    def find_principal(self, url=None):
        if url is None:
            url = self.find_dav()
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
        return utils.urlparse.urljoin(response.url, rv.text)

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
        rv = root.find('.//' + self._homeset_tag + '/{*}href')
        if rv is None:
            raise InvalidXMLResponse()
        return utils.urlparse.urljoin(response.url, rv.text)

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
            props = _merge_xml(response.findall('{*}propstat/{*}prop'))
            if props.find('{*}resourcetype/{*}' + self._resourcetype) is None:
                continue

            displayname = getattr(props.find('{*}displayname'), 'text', '')
            href = response.find('{*}href')
            if href is None:
                raise InvalidXMLResponse()
            href = utils.urlparse.urljoin(r.url, href.text)
            if href not in done:
                done.add(href)
                yield {'href': href, 'displayname': displayname}

    def discover(self):
        for x in self.find_collections():
            yield x

        # Another one of Radicale's specialties: Discovery is broken (returning
        # completely wrong URLs at every stage) as of version 0.9.
        # https://github.com/Kozea/Radicale/issues/196
        try:
            for x in self.find_collections(''):
                yield x
        except (InvalidXMLResponse, HTTPError, exceptions.Error):
            pass


class CalDiscover(Discover):
    _resourcetype = 'calendar'
    _homeset_xml = """
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
        <d:prop>
            <c:calendar-home-set />
        </d:prop>
    </d:propfind>
    """
    _homeset_tag = '{*}calendar-home-set'
    _well_known_uri = '/.well-known/caldav/'


class CardDiscover(Discover):
    _resourcetype = 'addressbook'
    _homeset_xml = """
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">
        <d:prop>
            <c:addressbook-home-set />
        </d:prop>
    </d:propfind>
    """
    _homeset_tag = '{*}addressbook-home-set'
    _well_known_uri = '/.well-known/carddav/'


class DavSession(object):
    '''
    A helper class to connect to DAV servers.
    '''

    def __init__(self, url, username='', password='', verify=True, auth=None,
                 useragent=USERAGENT, verify_fingerprint=None,
                 auth_cert=None):
        if username and not password:
            password = utils.get_password(username, url)

        self._settings = {
            'verify': prepare_verify(verify),
            'auth': prepare_auth(auth, username, password),
            'verify_fingerprint': verify_fingerprint,
            'cert': prepare_client_cert(auth_cert),
        }
        self.useragent = useragent
        self.url = url.rstrip('/') + '/'
        self.parsed_url = utils.urlparse.urlparse(self.url)
        self._session = None

    def request(self, method, path, **kwargs):
        url = self.url
        if path:
            url = utils.urlparse.urljoin(self.url, path)
        if self._session is None:
            self._session = requests_session()

        more = dict(self._settings)
        more.update(kwargs)
        return utils.request(method, url, session=self._session, **more)

    def get_default_headers(self):
        return {
            'User-Agent': self.useragent,
            'Content-Type': 'application/xml; charset=UTF-8'
        }


class DavStorage(Storage):

    __doc__ = '''
    :param url: Base URL or an URL to a collection.
    ''' + HTTP_STORAGE_PARAMETERS + '''
    :param unsafe_href_chars: Replace the given characters when generating
        hrefs. Defaults to ``'@'``.

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

    _session = None
    _repr_attributes = ('username', 'url')

    def __init__(self, url, username='', password='', verify=True, auth=None,
                 useragent=USERAGENT, unsafe_href_chars='@',
                 verify_fingerprint=None, auth_cert=None, **kwargs):
        super(DavStorage, self).__init__(**kwargs)

        url = url.rstrip('/') + '/'
        self.session = DavSession(url, username, password, verify, auth,
                                  useragent, verify_fingerprint,
                                  auth_cert)
        self.unsafe_href_chars = unsafe_href_chars

        # defined for _repr_attributes
        self.username = username
        self.url = url

    @classmethod
    def _get_session(cls, **kwargs):
        discover_args, _ = utils.split_dict(kwargs, lambda key: key in (
            'url', 'username', 'password', 'verify', 'auth', 'useragent',
            'verify_fingerprint', 'auth_cert',
        ))
        return DavSession(**discover_args)

    @classmethod
    def discover(cls, **kwargs):
        if kwargs.pop('collection', None) is not None:
            raise TypeError('collection argument must not be given.')

        d = cls.discovery_class(cls._get_session(**kwargs))
        for c in d.discover():
            url = c['href']
            collection = _get_collection_from_url(url)
            storage_args = dict(kwargs)
            storage_args.update({'url': url, 'collection': collection,
                                 'collection_human': c['displayname']})
            yield storage_args

    @classmethod
    def create_collection(cls, collection, **kwargs):
        if collection is None:
            collection = _get_collection_from_url(kwargs['url'])
        session = cls._get_session(**kwargs)
        d = cls.discovery_class(session)

        for c in cls.discover(**kwargs):
            if c['collection'] == collection:
                return c

        home = d.find_home()
        collection_url = '{0}/{1}'.format(home.rstrip('/'), collection)

        data = '''<?xml version="1.0" encoding="utf-8" ?>
        <D:mkcol xmlns:D="DAV:" xmlns:C="{0}">
            <D:set>
                <D:prop>
                    <D:resourcetype>
                        <D:collection/>
                        <C:{1}/>
                    </D:resourcetype>
                </D:prop>
            </D:set>
        </D:mkcol>
        '''.format(cls._dav_namespace, cls._dav_resourcetype)

        headers = d.session.get_default_headers()

        try:
            response = d.session.request('MKCOL', collection_url, data=data,
                                         headers=headers)
        except HTTPError as e:
            raise NotImplementedError(e)
        else:
            rv = dict(kwargs)
            rv['collection'] = collection
            rv['url'] = response.url
            return rv

    def _normalize_href(self, *args, **kwargs):
        return _normalize_href(self.session.url, *args, **kwargs)

    def _get_href(self, item):
        href = item.ident
        for char in self.unsafe_href_chars:
            href = href.replace(char, '_')
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
            href_xml.append('<D:href>{0}</D:href>'.format(_encode_href(href)))
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
                dav_logger.warning('Skipping {0}, the item content is missing.'
                                   .format(href))
                continue
            else:
                raw = raw.text
                if isinstance(raw, bytes):
                    raw = raw.decode(response.encoding)
                if isinstance(etag, bytes):
                    etag = etag.decode(response.encoding)

            try:
                hrefs_left.remove(href)
            except KeyError:
                if href in hrefs:
                    dav_logger.warning('Server sent item twice: {0}'
                                       .format(href))
                else:
                    dav_logger.warning('Server sent unsolicited item: {0}'
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
            _encode_href(href),
            data=item.raw.encode('utf-8'),
            headers=headers
        )
        etag = response.headers.get('etag', None)
        href = self._normalize_href(response.url)
        if not etag:
            item2, etag = self.get(href)
            assert item2.uid == item.uid
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
            _encode_href(href),
            headers=headers
        )

    def _parse_prop_responses(self, root, decoding_rounds=1):
        hrefs = set()
        for response in root.iter('{DAV:}response'):
            href = response.find('{DAV:}href')
            if href is None:
                dav_logger.error('Skipping response, href is missing.')
                continue

            href = self._normalize_href(href.text)
            for i in range(decoding_rounds):
                href = _decode_href(href)

            if href in hrefs:
                # Servers that send duplicate hrefs:
                # - Zimbra
                #   https://github.com/untitaker/vdirsyncer/issues/88
                # - Davmail
                #   https://github.com/untitaker/vdirsyncer/issues/144
                dav_logger.warning('Skipping identical href: {0!r}'
                                   .format(href))
                continue

            props = response.findall('{DAV:}propstat/{DAV:}prop')
            if not props:
                dav_logger.warning('Skipping {0!r}, properties are missing.'
                                   .format(href))
                continue
            else:
                props = _merge_xml(props)

            if props.find('{DAV:}resourcetype/{DAV:}collection') is not None:
		dav_logger.debug('Skipping {0!r}, is collection.'.format(href))
                continue

            etag = getattr(props.find('{DAV:}getetag'), 'text', '')
            if not etag:
                dav_logger.warning('Skipping {0!r}, etag property is missing.'
                                   .format(href))

            contenttype = getattr(props.find('{DAV:}getcontenttype'),
                                  'text', None)
            if not self._is_item_mimetype(contenttype):
                dav_logger.debug('Skipping {0!r}, {1!r} != {2!r}.'
                                 .format(href, contenttype,
                                         self.item_mimetype))
                continue

            hrefs.add(href)
            yield href, etag, props


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
    _dav_namespace = 'urn:ietf:params:xml:ns:caldav'
    _dav_resourcetype = 'calendar'

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
                 item_types=(), **kwargs):
        super(CaldavStorage, self).__init__(**kwargs)
        if not isinstance(item_types, (list, tuple)):
            raise ValueError('item_types must be a list.')

        self.item_types = tuple(item_types)
        if (start_date is None) != (end_date is None):
            raise ValueError('If start_date is given, '
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
            else:
                yield '<C:comp-filter name="VCALENDAR"/>'

    def list(self):
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
        # https://github.com/untitaker/vdirsyncer/issues/166
        # The default in CalDAV's calendar-queries is 0, but the examples use
        # an explicit value of 1 for querying items. it is extremely unclear in
        # the spec which values from WebDAV are actually allowed.
        headers['Depth'] = 1

        caldavfilters = self._get_list_filters(self.item_types,
                                               self.start_date, self.end_date)

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

    _dav_namespace = 'urn:ietf:params:xml:ns:carddav'
    _dav_resourcetype = 'addressbook'
    get_multi_data_query = '{urn:ietf:params:xml:ns:carddav}address-data'

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
        # with Zimbra. See https://github.com/untitaker/vdirsyncer/issues/83
        response = self.session.request('PROPFIND', '', data=data,
                                        headers=headers)
        root = _parse_xml(response.content)

        # Decode twice because ownCloud encodes twice.
        # See https://github.com/owncloud/contacts/issues/581
        rv = self._parse_prop_responses(root, decoding_rounds=2)
        for href, etag, prop in rv:
            yield href, etag
