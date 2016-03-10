'''
A storage type for accessing contact and calendar data from `remoteStorage
<https://remotestorage.io>`_. It is highly experimental.

A few things are hardcoded for now so the user doesn't have to specify those
things, and plugging in an account "just works".

We also use a custom ``data``-URI for the redirect in OAuth:

- There is no server that could be compromised.
- With a proper URL, ``access_token`` would be stored in the browser history.
  For some reason Firefox doesn't do that with ``data``-URIs.
- ``data``-URIs have no clear domain name that could prevent from phishing
  attacks. However, I don't see a way to phish without compromising the
  vdirsyncer installation, at which point any hope would already be lost.
- On the downside, redirect URIs are monstrous.

'''

import logging

import click

from .base import Item, Storage, normalize_meta_value
from .http import HTTP_STORAGE_PARAMETERS, prepare_client_cert, \
    prepare_verify
from .. import exceptions, utils

REDIRECT_URI = 'https://vdirsyncer.5apps.com/'
CLIENT_ID = 'https://vdirsyncer.5apps.com'
DRAFT_VERSION = '05'

logger = logging.getLogger(__name__)

urljoin = utils.compat.urlparse.urljoin
urlquote = utils.compat.urlquote


def _ensure_slash(dir):
    return dir.rstrip('/') + '/'


def _iter_listing(json):
    new_listing = '@context' in json  # draft-02 and beyond
    if new_listing:
        json = json['items']
    for name, info in utils.compat.iteritems(json):
        if not new_listing:
            info = {'ETag': info}
        yield name, info


class Session(object):

    def __init__(self, account, scope, verify=True, verify_fingerprint=None,
                 auth_cert=None, access_token=None, collection=None):
        from oauthlib.oauth2 import MobileApplicationClient
        from requests_oauthlib import OAuth2Session

        self.user, self.host = account.split('@')

        self._settings = {
            'cert': prepare_client_cert(auth_cert)
        }
        self._settings.update(prepare_verify(verify, verify_fingerprint))

        self.scope = scope + ':rw'
        self._session = OAuth2Session(
            CLIENT_ID, client=MobileApplicationClient(CLIENT_ID),
            scope=self.scope,
            redirect_uri=REDIRECT_URI,
            token={'access_token': access_token},
        )

        subpath = scope
        if collection:
            subpath = urljoin(_ensure_slash(scope),
                              _ensure_slash(urlquote(collection)))

        self._discover_endpoints(subpath)

        if not access_token:
            self._get_access_token()

    def request(self, method, path, **kwargs):
        url = self.endpoints['storage']
        if path:
            url = urljoin(url, path)

        settings = dict(self._settings)
        settings.update(kwargs)

        return utils.http.request(method, url,
                                  session=self._session, **settings)

    def _get_access_token(self):
        authorization_url, state = \
            self._session.authorization_url(self.endpoints['oauth'])

        click.echo('Opening {} ...'.format(authorization_url))
        try:
            utils.open_graphical_browser(authorization_url)
        except Exception as e:
            logger.warning(str(e))

        click.echo('Follow the instructions on the page.')
        raise exceptions.UserError('Aborted!')

    def _discover_endpoints(self, subpath):
        r = utils.http.request(
            'GET', 'https://{host}/.well-known/webfinger?resource=acct:{user}'
            .format(host=self.host, user=self.user),
            **self._settings
        )
        j = r.json()
        for link in j['links']:
            if 'remotestorage' in link['rel']:
                break

        storage = urljoin(_ensure_slash(link['href']),
                          _ensure_slash(subpath))
        props = link['properties']
        oauth = props['http://tools.ietf.org/html/rfc6749#section-4.2']
        self.endpoints = dict(storage=storage, oauth=oauth)


class RemoteStorage(Storage):
    __doc__ = '''
    :param account: remoteStorage account, ``"user@example.com"``.
    ''' + HTTP_STORAGE_PARAMETERS + '''
    '''

    storage_name = None
    item_mimetype = None
    fileext = None

    def __init__(self, account, verify=True, verify_fingerprint=None,
                 auth_cert=None, access_token=None, **kwargs):
        super(RemoteStorage, self).__init__(**kwargs)
        self.session = Session(
            account=account,
            verify=verify,
            verify_fingerprint=verify_fingerprint,
            auth_cert=auth_cert,
            access_token=access_token,
            collection=self.collection,
            scope=self.scope)

    @classmethod
    def discover(cls, **base_args):
        if base_args.pop('collection', None) is not None:
            raise TypeError('collection argument must not be given.')

        session_args, _ = utils.split_dict(base_args, lambda key: key in (
            'account', 'verify', 'auth', 'verify_fingerprint', 'auth_cert',
            'access_token'
        ))

        session = Session(scope=cls.scope, **session_args)

        try:
            r = session.request('GET', '')
        except exceptions.NotFoundError:
            return

        for name, info in _iter_listing(r.json()):
            if not name.endswith('/'):
                continue  # not a folder

            newargs = dict(base_args)
            newargs['collection'] = name.rstrip('/')
            yield newargs

    @classmethod
    def create_collection(cls, collection, **kwargs):
        # remoteStorage folders are autocreated.
        assert collection
        assert '/' not in collection
        kwargs['collection'] = collection
        return kwargs

    def list(self):
        try:
            r = self.session.request('GET', '')
        except exceptions.NotFoundError:
            return

        for name, info in _iter_listing(r.json()):
            if not name.endswith(self.fileext):
                continue

            etag = info['ETag']
            etag = '"' + etag + '"'
            yield name, etag

    def _put(self, href, item, etag):
        headers = {'Content-Type': self.item_mimetype + '; charset=UTF-8'}
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
        return href, response.headers['etag']

    def update(self, href, item, etag):
        assert etag
        href, etag = self._put(href, item, etag)
        return etag

    def upload(self, item):
        href = utils.generate_href(item.ident) + self.fileext
        return self._put(href, item, None)

    def delete(self, href, etag):
        headers = {'If-Match': etag}
        self.session.request('DELETE', href, headers=headers)

    def get(self, href):
        response = self.session.request('GET', href)
        return Item(response.text), response.headers['etag']

    def get_meta(self, key):
        try:
            return normalize_meta_value(self.session.request('GET', key).text)
        except exceptions.NotFoundError:
            return u''

    def set_meta(self, key, value):
        self.session.request(
            'PUT',
            key,
            data=normalize_meta_value(value).encode('utf-8'),
            headers={'Content-Type': 'text/plain; charset=utf-8'}
        )


class RemoteStorageContacts(RemoteStorage):
    __doc__ = '''
    remoteStorage contacts. Uses the `vdir_contacts` scope.
    ''' + RemoteStorage.__doc__

    storage_name = 'remotestorage_contacts'
    fileext = '.vcf'
    item_mimetype = 'text/vcard'
    scope = 'vdir_contacts'

    def __init__(self, **kwargs):
        if kwargs.get('collection'):
            raise ValueError(
                'No collections allowed for contacts, '
                'there is only one addressbook. '
                'Use the vcard groups construct to categorize your contacts '
                'into groups.'
            )

        super(RemoteStorageContacts, self).__init__(**kwargs)


class RemoteStorageCalendars(RemoteStorage):
    __doc__ = '''
    remoteStorage calendars. Uses the `vdir_calendars` scope.
    ''' + RemoteStorage.__doc__

    storage_name = 'remotestorage_calendars'
    fileext = '.ics'
    item_mimetype = 'text/icalendar'
    scope = 'vdir_calendars'

    def __init__(self, **kwargs):
        if not kwargs.get('collection'):
            raise ValueError('The collections parameter is required.')

        super(RemoteStorageCalendars, self).__init__(**kwargs)
