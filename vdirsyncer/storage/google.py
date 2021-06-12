import json
import logging
import os
import urllib.parse as urlparse

import click
from atomicwrites import atomic_write
from click_threading import get_ui_worker

from . import base
from . import dav
from .. import exceptions
from ..utils import checkdir
from ..utils import expand_path
from ..utils import open_graphical_browser

logger = logging.getLogger(__name__)


TOKEN_URL = "https://accounts.google.com/o/oauth2/v2/auth"
REFRESH_URL = "https://www.googleapis.com/oauth2/v4/token"

try:
    from requests_oauthlib import OAuth2Session

    have_oauth2 = True
except ImportError:
    have_oauth2 = False


class GoogleSession(dav.DAVSession):
    def __init__(self, token_file, client_id, client_secret, url=None):
        # Required for discovering collections
        if url is not None:
            self.url = url

        self.useragent = client_id
        self._settings = {}

        if not have_oauth2:
            raise exceptions.UserError("requests-oauthlib not installed")

        token_file = expand_path(token_file)
        ui_worker = get_ui_worker()
        ui_worker.put(lambda: self._init_token(token_file, client_id, client_secret))

    def _init_token(self, token_file, client_id, client_secret):
        token = None
        try:
            with open(token_file) as f:
                token = json.load(f)
        except OSError:
            pass
        except ValueError as e:
            raise exceptions.UserError(
                "Failed to load token file {}, try deleting it. "
                "Original error: {}".format(token_file, e)
            )

        def _save_token(token):
            checkdir(expand_path(os.path.dirname(token_file)), create=True)
            with atomic_write(token_file, mode="w", overwrite=True) as f:
                json.dump(token, f)

        self._session = OAuth2Session(
            client_id=client_id,
            token=token,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
            scope=self.scope,
            auto_refresh_url=REFRESH_URL,
            auto_refresh_kwargs={
                "client_id": client_id,
                "client_secret": client_secret,
            },
            token_updater=_save_token,
        )

        if not token:
            authorization_url, state = self._session.authorization_url(
                TOKEN_URL,
                # access_type and approval_prompt are Google specific
                # extra parameters.
                access_type="offline",
                approval_prompt="force",
            )
            click.echo(f"Opening {authorization_url} ...")
            try:
                open_graphical_browser(authorization_url)
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


class GoogleCalendarStorage(dav.CalDAVStorage):
    class session_class(GoogleSession):
        url = "https://apidata.googleusercontent.com/caldav/v2/"
        scope = ["https://www.googleapis.com/auth/calendar"]

    class discovery_class(dav.CalDiscover):
        @staticmethod
        def _get_collection_from_url(url):
            # Google CalDAV has collection URLs like:
            # /user/foouser/calendars/foocalendar/events/
            parts = url.rstrip("/").split("/")
            parts.pop()
            collection = parts.pop()
            return urlparse.unquote(collection)

    storage_name = "google_calendar"

    def __init__(
        self,
        token_file,
        client_id,
        client_secret,
        start_date=None,
        end_date=None,
        item_types=(),
        **kwargs,
    ):
        if not kwargs.get("collection"):
            raise exceptions.CollectionRequired()

        super().__init__(
            token_file=token_file,
            client_id=client_id,
            client_secret=client_secret,
            start_date=start_date,
            end_date=end_date,
            item_types=item_types,
            **kwargs,
        )

    # This is ugly: We define/override the entire signature computed for the
    # docs here because the current way we autogenerate those docs are too
    # simple for our advanced argspec juggling in `vdirsyncer.storage.dav`.
    __init__._traverse_superclass = base.Storage


class GoogleContactsStorage(dav.CardDAVStorage):
    class session_class(GoogleSession):
        # Google CardDAV is completely bonkers. Collection discovery doesn't
        # work properly, well-known URI takes us directly to single collection
        # from where we can't discover principal or homeset URIs (the PROPFINDs
        # 404).
        #
        # So we configure the well-known URI here again, such that discovery
        # tries collection enumeration on it directly. That appears to work.
        url = "https://www.googleapis.com/.well-known/carddav"
        scope = ["https://www.googleapis.com/auth/carddav"]

    class discovery_class(dav.CardDAVStorage.discovery_class):
        # Google CardDAV doesn't return any resourcetype prop.
        _resourcetype = None

    storage_name = "google_contacts"

    def __init__(self, token_file, client_id, client_secret, **kwargs):
        if not kwargs.get("collection"):
            raise exceptions.CollectionRequired()

        super().__init__(
            token_file=token_file,
            client_id=client_id,
            client_secret=client_secret,
            **kwargs,
        )

    # This is ugly: We define/override the entire signature computed for the
    # docs here because the current way we autogenerate those docs are too
    # simple for our advanced argspec juggling in `vdirsyncer.storage.dav`.
    __init__._traverse_superclass = base.Storage
