# -*- coding: utf-8 -*-

import json
import logging

import click

from . import base, dav
from .. import exceptions, utils

logger = logging.getLogger(__name__)


TOKEN_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
REFRESH_URL = 'https://www.googleapis.com/oauth2/v4/token'

try:
    from requests_oauthlib import OAuth2Session
    have_oauth2 = True
except ImportError:
    have_oauth2 = False


class GoogleSession(dav.DavSession):
    def __init__(self, token_file, client_id, client_secret, url=None):
        # Required for discovering collections
        if url is not None:
            self.url = url

        self.useragent = client_id
        self._settings = {}

        token_file = utils.expand_path(token_file)

        if not have_oauth2:
            raise exceptions.UserError('requests-oauthlib not installed')

        token = None
        try:
            with open(token_file) as f:
                token = json.load(f)
        except (OSError, IOError):
            pass

        def _save_token(token):
            with open(token_file, 'w') as f:
                json.dump(token, f)

        self._session = OAuth2Session(
            client_id=client_id,
            token=token,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob',
            scope=self.scope,
            auto_refresh_url=REFRESH_URL,
            auto_refresh_kwargs={
                'client_id': client_id,
                'client_secret': client_secret,
            },
            token_updater=_save_token
        )

        if not token:
            authorization_url, state = self._session.authorization_url(
                TOKEN_URL,
                # access_type and approval_prompt are Google specific
                # extra parameters.
                access_type='offline', approval_prompt='force')
            click.echo('Opening {} ...'.format(authorization_url))
            try:
                utils.open_graphical_browser(authorization_url)
            except Exception as e:
                logger.warning(str(e))

            click.echo("Follow the instructions on the page.")
            code = click.prompt("Paste obtained code")
            token = self._session.fetch_token(
                REFRESH_URL,
                code=code,
                # Google specific extra parameter used for client
                # authentication
                client_secret=client_secret,
            )
            # FIXME: Ugly
            _save_token(token)


GOOGLE_PARAMS_DOCS = '''
    :param token_file: A filepath where access tokens are stored.
    :param client_id/client_secret: OAuth credentials, obtained from the Google
        API Manager.
'''


class GoogleCalendarStorage(dav.CaldavStorage):
    __doc__ = '''Google calendar.

    Please refer to :storage:`caldav` regarding
    the ``item_types`` and timerange parameters.
    ''' + GOOGLE_PARAMS_DOCS

    class session_class(GoogleSession):
        url = 'https://apidata.googleusercontent.com/caldav/v2/'
        scope = ['https://www.googleapis.com/auth/calendar']

    class discovery_class(dav.CalDiscover):
        @staticmethod
        def _get_collection_from_url(url):
            # Google CalDAV has collection URLs like:
            # /user/foouser/calendars/foocalendar/events/
            parts = url.rstrip('/').split('/')
            parts.pop()
            collection = parts.pop()
            return utils.compat.urlunquote(collection)

    storage_name = 'google_calendar'

    def __init__(self, token_file, client_id, client_secret, start_date=None,
                 end_date=None, item_types=(), **kwargs):
        super(GoogleCalendarStorage, self).__init__(
            token_file=token_file, client_id=client_id,
            client_secret=client_secret, start_date=start_date,
            end_date=end_date, item_types=item_types,
            **kwargs
        )

    # This is ugly: We define/override the entire signature computed for the
    # docs here because the current way we autogenerate those docs are too
    # simple for our advanced argspec juggling in `vdirsyncer.storage.dav`.
    __init__._traverse_superclass = base.Storage


class GoogleContactsStorage(dav.CarddavStorage):
    __doc__ = '''Google contacts.

    .. note: Google's CardDAV implementation is allegedly a disaster in terms
        of data safety. See `this blog post
        <https://evertpot.com/google-carddav-issues/>`_ for the details.
        Always back up your data.
    ''' + GOOGLE_PARAMS_DOCS

    class session_class(GoogleSession):
        # Apparently Google wants us to submit a PROPFIND to the well-known
        # URL, instead of looking for a redirect.
        url = 'https://www.googleapis.com/.well-known/carddav/'
        scope = ['https://www.googleapis.com/auth/carddav']

    storage_name = 'google_contacts'

    def __init__(self, token_file, client_id, client_secret, **kwargs):
        super(GoogleContactsStorage, self).__init__(
            token_file=token_file, client_id=client_id,
            client_secret=client_secret,
            **kwargs
        )

    # This is ugly: We define/override the entire signature computed for the
    # docs here because the current way we autogenerate those docs are too
    # simple for our advanced argspec juggling in `vdirsyncer.storage.dav`.
    __init__._traverse_superclass = base.Storage
