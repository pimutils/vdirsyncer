from __future__ import annotations

import pytz
from icalendar import Calendar, Todo
from datetime import datetime
import json
import logging
import os
import urllib.parse as urlparse
import wsgiref.simple_server
import wsgiref.util
from pathlib import Path
from threading import Thread

import aiohttp
import click

from .. import exceptions
from ..utils import atomic_write
from ..utils import checkdir
from ..utils import expand_path
from ..utils import open_graphical_browser
from ..vobject import Item
from . import base
from . import dav
from .google_helpers import _RedirectWSGIApp
from .google_helpers import _WSGIRequestHandler
from googleapiclient.errors import HttpError

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
        self._redirect_uri = None

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
        """Return a new OAuth session for requests.

        Accesses the self.redirect_uri field (str): the URI to redirect
        authentication to. Should be a loopback address for a local server that
        follows the process detailed in
        https://developers.google.com/identity/protocols/oauth2/native-app.
        """

        return OAuth2Session(
            client_id=self._client_id,
            token=self._token,
            redirect_uri=self._redirect_uri,
            scope=self.scope,
            auto_refresh_url=REFRESH_URL,
            auto_refresh_kwargs={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            token_updater=self._save_token,
            connector=self.connector,
            connector_owner=False,
            trust_env=True,
        )

    async def _init_token(self):
        try:
            with self._token_file.open() as f:
                self._token = json.load(f)
        except FileNotFoundError:
            pass
        except ValueError as e:
            raise exceptions.UserError(
                f"Failed to load token file {self._token_file}, try deleting it. "
                f"Original error: {e}"
            )

        if not self._token:
            # Some times a task stops at this `async`, and another continues the flow.
            # At this point, the user has already completed the flow, but is prompeted
            # for a second one.
            wsgi_app = _RedirectWSGIApp("Successfully obtained token.")
            wsgiref.simple_server.WSGIServer.allow_reuse_address = False
            host = "127.0.0.1"
            local_server = wsgiref.simple_server.make_server(
                host, 0, wsgi_app, handler_class=_WSGIRequestHandler
            )
            thread = Thread(target=local_server.handle_request)
            thread.start()
            self._redirect_uri = f"http://{host}:{local_server.server_port}"
            async with self._session as session:
                # Fail fast if the address is occupied

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
                thread.join()
                logger.debug("server handled request!")

                # Note: using https here because oauthlib is very picky that
                # OAuth 2.0 should only occur over https.
                authorization_response = wsgi_app.last_request_uri.replace(
                    "http", "https", 1
                )
                logger.debug(f"authorization_response: {authorization_response}")
                self._token = await session.fetch_token(
                    REFRESH_URL,
                    authorization_response=authorization_response,
                    # Google specific extra param used for client authentication:
                    client_secret=self._client_secret,
                )
                logger.debug(f"token: {self._token}")
                local_server.server_close()

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
            raise exceptions.CollectionRequired

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
            raise exceptions.CollectionRequired

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


class GoogleTasksStorage(base.Storage):
    SCOPES = ["https://www.googleapis.com/auth/tasks"]
    read_only = False
    no_delete = False
    storage_name = "google_tasks"
    authenticated_service = None

    def __init__(self, **kwargs):
        super().__init__(
            kwargs["collection"],
            self.read_only,
            self.no_delete,
            kwargs["instance_name"],
        )
        self.tasklist_id = kwargs["collection"]
        self.service = GoogleTasksStorage.get_authenticated_service(
            kwargs["token_file"], kwargs["client_id"], kwargs["client_secret"]
        )

    async def list(self):
        tasks_result = (
            self.service.tasks()
            .list(tasklist=self.tasklist_id, showCompleted=True, showHidden=True)
            .execute()
        )
        tasks = tasks_result.get("items", [])
        for t in tasks:
            yield t["id"], t["etag"]

    async def get(self, href: str):
        tasks_result = (
            self.service.tasks().get(tasklist=self.tasklist_id, task=href).execute()
        )
        ics = GoogleTasksStorage.task_to_ics(tasks_result, self.tasklist_id)
        return (Item(ics), tasks_result["etag"])

    async def upload(self, item: Item):
        try:
            task = GoogleTasksStorage.ics_to_task(item.raw)
            tasks_result = (
                self.service.tasks()
                .insert(tasklist=self.tasklist_id, body=task)
                .execute()
            )
            return tasks_result["id"], tasks_result["etag"]
        except HttpError as e:
            logger.debug(f"GTasks API error :\n {e.content}")
            raise e

    async def update(self, href: str, item: Item, etag: str):
        tasks_result = (
            self.service.tasks().get(tasklist=self.tasklist_id, task=href).execute()
        )
        if tasks_result["etag"] != etag:
            raise exceptions.WrongEtagError(etag, tasks_result["etag"])
        task = GoogleTasksStorage.ics_to_task(item.raw, tasks_result)
        tasks_result = (
            self.service.tasks().insert(tasklist=self.tasklist_id, body=task).execute()
        )
        return tasks_result["id"], tasks_result["etag"]

    async def delete(self, href: str, etag: str):
        try:
            self.service.tasks().delete(tasklist=self.tasklist_id, task=href).execute()
        except HttpError as e:
            logger.debug(f"GTasks API error:\n{e.content}")
            raise e

    async def get_meta(self, key: str):
        if key == "displayname":
            tasks_result = (
                self.service.tasklists().get(tasklist=self.tasklist_id).execute()
            )
            return tasks_result["title"]
        else:
            return None

    @classmethod
    async def discover(cls, **kwargs):
        service = GoogleTasksStorage.get_authenticated_service(
            kwargs["token_file"], kwargs["client_id"], kwargs["client_secret"]
        )
        tasks_result = service.tasklists().list().execute()
        for tl in tasks_result["items"]:
            print(f"tl: {tl['id']} / {tl['title']} etag: {tl['etag']}")
            yield dict(collection=tl["id"], **kwargs)

    @staticmethod
    def get_authenticated_service(token_file: str, client_id: str, client_secret: str):
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None
        token_dir = os.path.dirname(token_file)
        if not os.path.isdir(token_dir):
            os.makedirs(token_dir)
        if os.path.isfile(token_file):
            creds = Credentials.from_authorized_user_file(
                token_file, GoogleTasksStorage.SCOPES
            )
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_config(
                    {
                        "installed": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "auth_uri": TOKEN_URL,
                            "token_uri": REFRESH_URL,
                            "redirect_uris": [
                                "urn:ietf:wg:oauth:2.0:oob",
                                "http://localhost",
                            ],
                        }
                    },
                    GoogleTasksStorage.SCOPES,
                )
                creds = flow.run_local_server(port=0)
                with open(token_file, "w") as token:
                    token.write(creds.to_json())

        service = build("tasks", "v1", credentials=creds)
        return service

    @staticmethod
    def task_to_ics(task, calendar_name: str):
        """
        Convert a Google Task to an iCalendar (ICS) event.

        Args:
            task (dict): A task returned from the Google Tasks API.
            calendar_name (str): Name to assign to the calendar.

        Returns:
            str: An ICS file content string.
        """
        now = datetime.now(pytz.utc)
        cal = Calendar()
        cal.add("prodid", "-//Google Tasks to ICS//mxm.dk//")
        cal.add("version", "2.0")
        cal.add("X-WR-CALNAME", calendar_name)

        todo = Todo()
        todo.add("uid", task.get("id"))
        todo.add("summary", task.get("title", "Untitled Task"))
        notes = task.get("notes")
        if notes:
            todo.add("description", notes)

        updated = task.get("updated")
        if updated:
            dt = datetime.fromisoformat(task.get("updated").rstrip("Z"))
            todo.add("dtstart", dt)
        else:
            todo.add("dtstart", now)
        due = task.get("due")
        if due:
            dt = datetime.fromisoformat(due.rstrip("Z"))
            todo.add("due", dt)

        todo.add(
            "status",
            "COMPLETED" if task.get("status") == "completed" else "NEEDS-ACTION",
        )

        cal.add_component(todo)
        return cal.to_ical().decode("utf-8")

    @staticmethod
    def ics_to_task(ics: str, task_to_update=None):
        task = {}
        cal = Calendar.from_ical(ics)
        todo = cal.walk("VTODO")
        if todo is None:
            raise Exception("ICS contains no VTODO")
        todo = todo[0]
        # task['id'] = str(todo['UID'])
        task["title"] = str(todo["SUMMARY"])
        if "DESCRIPTION" in todo.keys():
            task["notes"] = str(todo.get("DESCRIPTION"))
        task["status"] = (
            "needsAction"
            if "STATUS" not in todo.keys() or todo["STATUS"] != "COMPLETED"
            else "completed"
        )
        if "DUE" in todo.keys():
            task["due"] = todo["DUE"].dt.isoformat().replace("+00:00", "Z")
        return task
