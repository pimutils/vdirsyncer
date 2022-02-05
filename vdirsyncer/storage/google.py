import json
import logging
import os
import urllib.parse as urlparse
from pathlib import Path

import aiohttp
import click
from atomicwrites import atomic_write

from .. import exceptions
from ..utils import checkdir
from ..utils import expand_path
from ..utils import open_graphical_browser
from . import base
from . import dav

logger = logging.getLogger(__name__)


TOKEN_URL = "https://accounts.google.com/o/oauth2/v2/auth"
REFRESH_URL = "https://www.googleapis.com/oauth2/v4/token"

try:
    from aiohttp_oauthlib import OAuth2Session

    have_oauth2 = True
except ImportError:
    have_oauth2 = False


class GoogleSession(dav.DAVSession):
    def __init__(
        self,
        token_file,
        client_id,
        client_secret,
        url=None,
        *,
        connector: aiohttp.BaseConnector,
    ):
        if not have_oauth2:
            raise exceptions.UserError("aiohttp-oauthlib not installed")

        # Required for discovering collections
        if url is not None:
            self.url = url

        self.useragent = client_id
        self._settings = {}
        self.connector = connector

        self._token_file = Path(expand_path(token_file))
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = None

    async def request(self, method, path, **kwargs):
        if not self._token:
            await self._init_token()

        return await super().request(method, path, **kwargs)

    async def _save_token(self, token):
        """Helper function called by OAuth2Session when a token is updated."""
        checkdir(expand_path(os.path.dirname(self._token_file)), create=True)
        with atomic_write(self._token_file, mode="w", overwrite=True) as f:
            json.dump(token, f)

    @property
    def _session(self):
        """Return a new OAuth session for requests."""

        return OAuth2Session(
            client_id=self._client_id,
            token=self._token,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
            scope=self.scope,
            auto_refresh_url=REFRESH_URL,
            auto_refresh_kwargs={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            token_updater=self._save_token,
            connector=self.connector,
            connector_owner=False,
        )

    async def _init_token(self):
        try:
            with self._token_file.open() as f:
                self._token = json.load(f)
        except FileNotFoundError:
            pass
        except ValueError as e:
            raise exceptions.UserError(
                "Failed to load token file {}, try deleting it. "
                "Original error: {}".format(self._token_file, e)
            )

        if not self._token:
            # Some times a task stops at this `async`, and another continues the flow.
            # At this point, the user has already completed the flow, but is prompeted
            # for a second one.
            async with self._session as session:
                authorization_url, state = session.authorization_url(
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

                self._token = await session.fetch_token(
                    REFRESH_URL,
                    code=code,
                    # Google specific extra param used for client authentication:
                    client_secret=self._client_secret,
                )

            # FIXME: Ugly
            await self._save_token(self._token)


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
    __init__._traverse_superclass = base.Storage  # type: ignore


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

    class discovery_class(dav.CardDiscover):
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
    __init__._traverse_superclass = base.Storage  # type: ignore
