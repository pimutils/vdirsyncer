# -*- coding: utf-8 -*-
'''
    vdirsyncer.storage.dav
    ~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''
import datetime

from lxml import etree

from requests import session as requests_session

from .. import exceptions, log, utils
from .base import Item, Storage
from .http import USERAGENT, prepare_auth, prepare_verify


dav_logger = log.get(__name__)

CALDAV_DT_FORMAT = '%Y%m%dT%H%M%SZ'


def _normalize_href(base, href, decoding_rounds=1):
    '''Normalize the href to be a path only relative to hostname and
    schema.'''
    if not href:
        raise ValueError(href)
    x = utils.urlparse.urljoin(base, href)
    x = utils.urlparse.urlsplit(x).path

    for i in range(decoding_rounds):
        x = utils.compat.urlunquote(x)

    x = utils.compat.urlquote(x, '/@')
    return x


class Discover(object):

    xml_home = None
    xml_collection = None

    str_homeset = None

    def __init__(self, session):
        self.session = session

    def _find_principal(self):
        """tries to find the principal URL of the user
        :returns: iterable (but should be only of element) of urls
        :rtype: iterable(unicode)

        """
        headers = self.session.get_default_headers()
        headers['Depth'] = 0
        body = """
        <d:propfind xmlns:d="DAV:">
            <d:prop>
                <d:current-user-principal />
            </d:prop>
        </d:propfind>
        """
        response = self.session.request('PROPFIND', '', headers=headers,
                                        data=body)
        root = etree.XML(response.content)

        for element in root.iter('{*}current-user-principal'):
            for principal in element.iter():  # should be only one
                if principal.tag.endswith('href'):
                    yield principal.text

    def discover(self):
        """discover all the user's CalDAV or CardDAV collections on the server
        :returns: a list of the user's collections (as urls)
        :rtype: list(unicode)
        """
        for principal in list(self._find_principal()) or ['']:
            for home in list(self._find_home(principal)) or ['']:
                for collection in self._find_collections(home):
                    yield collection

    def _find_home(self, principal):
        headers = self.session.get_default_headers()
        headers['Depth'] = 0
        response = self.session.request('PROPFIND', principal, headers=headers,
                                        data=self.xml_home,
                                        is_subpath=False)

        root = etree.fromstring(response.content)
        for element in root.iter(self.str_homeset):
            for homeset in element.iter():
                if homeset.tag.endswith('href'):
                    yield homeset.text

    def _find_collections(self, home):
        raise NotImplementedError()


class CalDiscover(Discover):

    xml_home = """
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
        <d:prop>
            <c:calendar-home-set />
        </d:prop>
    </d:propfind>
    """
    xml_collection = """
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
        <d:prop>
            <d:resourcetype />
            <d:displayname />
            <c:supported-calendar-component-set />
        </d:prop>
    </d:propfind>
    """
    str_homeset = '{*}calendar-home-set'

    def _find_collections(self, home):
        """find all CalDAV collections under `home`"""

        headers = self.session.get_default_headers()
        headers['Depth'] = 1
        response = self.session.request('PROPFIND', home, headers=headers,
                                        data=self.xml_collection,
                                        is_subpath=False)
        root = etree.XML(response.content)
        for response in root.iter('{*}response'):
            prop = response.find('{*}propstat/{*}prop')
            if prop.find('{*}resourcetype/{*}calendar') is None:
                continue

            displayname = prop.find('{*}displayname')
            collection = {
                'href': response.find('{*}href').text,
                'displayname': '' if displayname is None else displayname.text
            }

            component_set = prop.find('{*}supported-calendar-component-set')
            if component_set is not None:
                for one in component_set:
                    collection[one.get('name')] = True

            yield collection


class CardDiscover(Discover):
    xml_home = """
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">
        <d:prop>
            <c:addressbook-home-set />
        </d:prop>
    </d:propfind>
    """
    xml_collection = """
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:cardav">
        <d:prop>
            <d:resourcetype />
            <c:addressbook />
        </d:prop>
    </d:propfind>
    """
    str_homeset = '{*}addressbook-home-set'

    def _find_collections(self, home):
        """find all CardDAV collections under `home`"""
        headers = self.session.get_default_headers()
        headers['Depth'] = 1
        response = self.session.request('PROPFIND', home, headers=headers,
                                        data=self.xml_collection,
                                        is_subpath=False)

        root = etree.XML(response.content)
        for response in root.iter('{*}response'):
            prop = response.find('{*}propstat/{*}prop')
            if prop.find('{*}resourcetype/{*}addressbook') is None:
                continue

            displayname = prop.find('{*}displayname')
            yield {
                'href': response.find('{*}href').text,
                'displayname': '' if displayname is None else displayname.text
            }


class DavSession(object):
    '''
    A helper class to connect to DAV servers.
    '''

    def __init__(self, url, username='', password='', verify=True, auth=None,
                 useragent=USERAGENT, dav_header=None):
        if username and not password:
            password = utils.get_password(username, url)

        self._settings = {
            'verify': prepare_verify(verify),
            'auth': prepare_auth(auth, username, password)
        }
        self.useragent = useragent
        self.url = url.rstrip('/') + '/'
        self.parsed_url = utils.urlparse.urlparse(self.url)
        self.dav_header = dav_header
        self._session = None

    def request(self, method, path, data=None, headers=None,
                is_subpath=True):
        url = self.url
        if path:
            url = utils.urlparse.urljoin(self.url, path)
        assert url.startswith(self.url) or not is_subpath
        if self._session is None:
            self._session = requests_session()
            self._check_dav_header()
        return utils.request(method, url, data=data, headers=headers,
                             session=self._session, **self._settings)

    def _check_dav_header(self):
        if self.dav_header is None:
            return
        headers = self.get_default_headers()
        headers['Depth'] = 1
        response = self.request(
            'OPTIONS',
            '',
            headers=headers
        )
        if self.dav_header not in response.headers.get('DAV', ''):
            raise ValueError('URL is not a collection')

    def get_default_headers(self):
        return {
            'User-Agent': self.useragent,
            'Content-Type': 'application/xml; charset=UTF-8'
        }


class DavStorage(Storage):

    '''
    .. note::

        Please also see :doc:`server_support` for very important information,
        as changing some of the default options might be very dangerous with
        some servers.

    :param url: Base URL or an URL to a collection.
    :param username: Username for authentication.
    :param password: Password for authentication.
    :param verify: Verify SSL certificate, default True. This can also be a
        local path to a self-signed SSL certificate.
    :param auth: Optional. Either ``basic``, ``digest`` or ``guess``. Default
        ``guess``. If you know yours, consider setting it explicitly for
        performance.
    :param useragent: Default ``vdirsyncer``.
    :param unsafe_href_chars: Replace the given characters when generating
        hrefs. Defaults to ``'@'``.
    '''

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
    # The Discover subclass to use
    discovery_class = None

    _session = None
    _repr_attributes = ('username', 'url')

    def __init__(self, url, username='', password='', collection=None,
                 verify=True, auth=None, useragent=USERAGENT,
                 unsafe_href_chars='@', **kwargs):
        super(DavStorage, self).__init__(**kwargs)

        url = url.rstrip('/') + '/'
        if collection is not None:
            url = utils.urlparse.urljoin(url, collection)
        self.session = DavSession(url, username, password, verify, auth,
                                  useragent, dav_header=self.dav_header)
        self.collection = collection
        self.unsafe_href_chars = unsafe_href_chars

        # defined for _repr_attributes
        self.username = username
        self.url = url

    @classmethod
    def discover(cls, url, **kwargs):
        if kwargs.pop('collection', None) is not None:
            raise TypeError('collection argument must not be given.')
        discover_args, _ = utils.split_dict(kwargs, lambda key: key in (
            'username', 'password', 'verify', 'auth', 'useragent'
        ))
        d = cls.discovery_class(DavSession(
            url=url, dav_header=None, **discover_args))
        for c in d.discover():
            base, collection = c['href'].rstrip('/').rsplit('/', 1)
            s = cls(url=base, collection=collection, **kwargs)
            s.displayname = c['displayname']
            yield s

    def _normalize_href(self, *args, **kwargs):
        return _normalize_href(self.session.url, *args, **kwargs)

    def _get_href(self, item):
        href = item.ident
        for char in self.unsafe_href_chars:
            href = item.ident.replace(char, '_')
        return self._normalize_href(href + self.fileext)

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
        response = self.session.request(
            'REPORT',
            '',
            data=data,
            headers=self.session.get_default_headers()
        )
        root = etree.XML(response.content)  # etree only can handle bytes
        rv = []
        hrefs_left = set(hrefs)
        for element in root.iter('{DAV:}response'):
            href = self._normalize_href(
                element.find('{DAV:}href').text)
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

    def _put(self, href, item, etag):
        headers = self.session.get_default_headers()
        headers['Content-Type'] = self.item_mimetype
        if etag is None:
            headers['If-None-Match'] = '*'
        else:
            assert etag[0] == etag[-1] == '"'
            headers['If-Match'] = etag

        response = self.session.request(
            'PUT',
            href,
            data=item.raw.encode('utf-8'),
            headers=headers
        )
        etag = response.headers.get('etag', None)
        if not etag:
            item2, etag = self.get(href)
            assert item2.uid == item.uid
        return href, etag

    def update(self, href, item, etag):
        href = self._normalize_href(href)
        if etag is None:
            raise ValueError('etag must be given and must not be None.')
        href, etag = self._put(href, item, etag)
        return etag

    def upload(self, item):
        href = self._get_href(item)
        return self._put(href, item, None)

    def delete(self, href, etag):
        href = self._normalize_href(href)
        headers = self.session.get_default_headers()
        assert etag[0] == etag[-1] == '"'
        headers.update({
            'If-Match': etag
        })

        self.session.request(
            'DELETE',
            href,
            headers=headers
        )

    def _dav_query(self, xml):
        headers = self.session.get_default_headers()

        # CardDAV: The request MUST include a Depth header. The scope of the
        # query is determined by the value of the Depth header. For example,
        # to query all address object resources in an address book collection,
        # the REPORT would use the address book collection as the Request- URI
        # and specify a Depth of 1 or infinity.
        # http://tools.ietf.org/html/rfc6352#section-8.6
        #
        # CalDAV:
        # The request MAY include a Depth header.  If no Depth header is
        # included, Depth:0 is assumed.
        # http://tools.ietf.org/search/rfc4791#section-7.8
        headers['Depth'] = 'infinity'
        response = self.session.request(
            'REPORT',
            '',
            data=xml,
            headers=headers
        )
        root = etree.XML(response.content)
        for element in root.iter('{DAV:}response'):
            etag = element.find('{DAV:}propstat').find(
                '{DAV:}prop').find('{DAV:}getetag').text
            href = self._normalize_href(element.find('{DAV:}href').text)
            yield href, etag


class CaldavStorage(DavStorage):

    __doc__ = '''
    CalDAV. Usable as ``caldav`` in the config file.

    You can set a timerange to synchronize with the parameters ``start_date``
    and ``end_date``. Inside those parameters, you can use any Python
    expression to return a valid :py:class:`datetime.datetime` object. For
    example, the following would synchronize the timerange from one year in the
    past to one year in the future::

        start_date = datetime.now() - timedelta(days=365)
        end_date = datetime.now() + timedelta(days=365)

    Either both or none have to be specified. The default is to synchronize
    everything.

    ''' + DavStorage.__doc__ + '''
    :param start_date: Start date of timerange to show, default -inf.
    :param end_date: End date of timerange to show, default +inf.
    :param item_types: Comma-separated collection types to show from the
        server. Dependent on server functionality, no clientside validation of
        results. The empty value ``''`` is the same as ``'VTODO, VEVENT,
        VJOURNAL'``.

    '''

    storage_name = 'caldav'
    fileext = '.ics'
    item_mimetype = 'text/calendar'
    dav_header = 'calendar-access'
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

    def __init__(self, start_date=None, end_date=None,
                 item_types='VTODO, VEVENT', **kwargs):
        super(CaldavStorage, self).__init__(**kwargs)
        if isinstance(item_types, str):
            item_types = filter(bool,
                                (x.strip() for x in item_types.split(',')))
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
                    <D:getetag/>
                </D:prop>
                <C:filter>
                {caldavfilter}
                </C:filter>
            </C:calendar-query>'''

        hrefs = set()

        caldavfilters = self._get_list_filters(self.item_types,
                                               self.start_date, self.end_date)

        for caldavfilter in caldavfilters:
            xml = data.format(caldavfilter=caldavfilter)
            for href, etag in self._dav_query(xml):
                if href in hrefs:
                    # Can't do stronger assertion here, see
                    # https://github.com/untitaker/vdirsyncer/issues/88
                    dav_logger.warning('Skipping identical href: {}'
                                       .format(href))
                    continue

                hrefs.add(href)
                yield href, etag


class CarddavStorage(DavStorage):

    __doc__ = '''
    CardDAV. Usable as ``carddav`` in the config file.
    ''' + DavStorage.__doc__

    storage_name = 'carddav'
    fileext = '.vcf'
    item_mimetype = 'text/vcard'
    dav_header = 'addressbook'
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

        root = etree.XML(response.content)
        hrefs = set()
        for element in root.iter('{DAV:}response'):
            prop = element.find('{DAV:}propstat').find('{DAV:}prop')

            resource_type = prop.find('{DAV:}resourcetype')
            if resource_type.find('{DAV:}collection') is not None:
                continue

            content_type = prop.find('{DAV:}getcontenttype')
            # different servers give different getcontenttypes:
            # "text/vcard", "text/x-vcard", "text/x-vcard; charset=utf-8",
            # "text/directory;profile=vCard", "text/directory",
            # "text/vcard; charset=utf-8"
            if 'vcard' not in content_type.text.lower():
                continue

            # Decode twice because ownCloud encodes twice.
            # See https://github.com/owncloud/contacts/issues/581
            href = self._normalize_href(element.find('{DAV:}href').text,
                                        decoding_rounds=2)
            etag = prop.find('{DAV:}getetag').text

            if href in hrefs:
                # Can't do stronger assertion here, see
                # https://github.com/untitaker/vdirsyncer/issues/88
                dav_logger.warning('Skipping identical href: {}'.format(href))
                continue

            hrefs.add(href)
            yield href, etag
