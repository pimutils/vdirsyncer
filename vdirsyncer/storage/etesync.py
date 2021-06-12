import binascii
import contextlib
import functools
import logging
import os

import atomicwrites
import click

try:
    import etesync
    import etesync.exceptions
    from etesync import AddressBook, Contact, Calendar, Event

    has_etesync = True
except ImportError:
    has_etesync = False
    AddressBook = Contact = Calendar = Event = None

from .. import exceptions
from ..cli.utils import assert_permissions
from ..utils import checkdir
from ..vobject import Item

from .base import Storage


logger = logging.getLogger(__name__)


def _writing_op(f):
    @functools.wraps(f)
    def inner(self, *args, **kwargs):
        if not self._at_once:
            self._sync_journal()
        rv = f(self, *args, **kwargs)
        if not self._at_once:
            self._sync_journal()
        return rv

    return inner


class _Session:
    def __init__(self, email, secrets_dir, server_url=None, db_path=None):
        if not has_etesync:
            raise exceptions.UserError("Dependencies for etesync are not " "installed.")
        server_url = server_url or etesync.API_URL
        self.email = email
        self.secrets_dir = os.path.join(secrets_dir, email + "/")

        self._auth_token_path = os.path.join(self.secrets_dir, "auth_token")
        self._key_path = os.path.join(self.secrets_dir, "key")

        auth_token = self._get_auth_token()
        if not auth_token:
            password = click.prompt(
                "Enter service password for {}".format(self.email), hide_input=True
            )
            auth_token = etesync.Authenticator(server_url).get_auth_token(
                self.email, password
            )
            self._set_auth_token(auth_token)

        self._db_path = db_path or os.path.join(self.secrets_dir, "db.sqlite")
        self.etesync = etesync.EteSync(
            email, auth_token, remote=server_url, db_path=self._db_path
        )

        key = self._get_key()
        if not key:
            password = click.prompt("Enter key password", hide_input=True)
            click.echo(f"Deriving key for {self.email}")
            self.etesync.derive_key(password)
            self._set_key(self.etesync.cipher_key)
        else:
            self.etesync.cipher_key = key

    def _get_auth_token(self):
        try:
            with open(self._auth_token_path) as f:
                return f.read().strip() or None
        except OSError:
            pass

    def _set_auth_token(self, token):
        checkdir(os.path.dirname(self._auth_token_path), create=True)
        with atomicwrites.atomic_write(self._auth_token_path) as f:
            f.write(token)
        assert_permissions(self._auth_token_path, 0o600)

    def _get_key(self):
        try:
            with open(self._key_path, "rb") as f:
                return f.read()
        except OSError:
            pass

    def _set_key(self, content):
        checkdir(os.path.dirname(self._key_path), create=True)
        with atomicwrites.atomic_write(self._key_path, mode="wb") as f:
            f.write(content)
        assert_permissions(self._key_path, 0o600)


class EtesyncStorage(Storage):
    _collection_type = None
    _item_type = None
    _at_once = False

    def __init__(self, email, secrets_dir, server_url=None, db_path=None, **kwargs):
        if kwargs.get("collection", None) is None:
            raise ValueError("Collection argument required")

        self._session = _Session(email, secrets_dir, server_url, db_path)
        super().__init__(**kwargs)
        self._journal = self._session.etesync.get(self.collection)

    def _sync_journal(self):
        self._session.etesync.sync_journal(self.collection)

    @classmethod
    def discover(cls, email, secrets_dir, server_url=None, db_path=None, **kwargs):
        if kwargs.get("collection", None) is not None:
            raise TypeError("collection argument must not be given.")
        session = _Session(email, secrets_dir, server_url, db_path)
        assert cls._collection_type
        session.etesync.sync_journal_list()
        for entry in session.etesync.list():
            if isinstance(entry.collection, cls._collection_type):
                yield dict(
                    email=email,
                    secrets_dir=secrets_dir,
                    db_path=db_path,
                    collection=entry.uid,
                    **kwargs,
                )
            else:
                logger.debug(f"Skipping collection: {entry!r}")

    @classmethod
    def create_collection(
        cls, collection, email, secrets_dir, server_url=None, db_path=None, **kwargs
    ):
        session = _Session(email, secrets_dir, server_url, db_path)
        content = {"displayName": collection}
        c = cls._collection_type.create(
            session.etesync, binascii.hexlify(os.urandom(32)).decode(), content
        )
        c.save()
        session.etesync.sync_journal_list()
        return dict(
            collection=c.journal.uid,
            email=email,
            secrets_dir=secrets_dir,
            db_path=db_path,
            server_url=server_url,
            **kwargs,
        )

    def list(self):
        self._sync_journal()
        for entry in self._journal.collection.list():
            item = Item(entry.content)
            yield str(entry.uid), item.hash

    def get(self, href):
        try:
            item = Item(self._journal.collection.get(href).content)
        except etesync.exceptions.DoesNotExist as e:
            raise exceptions.NotFoundError(e)
        return item, item.hash

    @_writing_op
    def upload(self, item):
        try:
            entry = self._item_type.create(self._journal.collection, item.raw)
            entry.save()
        except etesync.exceptions.DoesNotExist as e:
            raise exceptions.NotFoundError(e)
        except etesync.exceptions.AlreadyExists as e:
            raise exceptions.AlreadyExistingError(e)
        return item.uid, item.hash

    @_writing_op
    def update(self, href, item, etag):
        try:
            entry = self._journal.collection.get(href)
        except etesync.exceptions.DoesNotExist as e:
            raise exceptions.NotFoundError(e)
        old_item = Item(entry.content)
        if old_item.hash != etag:
            raise exceptions.WrongEtagError(etag, old_item.hash)
        entry.content = item.raw
        entry.save()
        return item.hash

    @_writing_op
    def delete(self, href, etag):
        try:
            entry = self._journal.collection.get(href)
            old_item = Item(entry.content)
            if old_item.hash != etag:
                raise exceptions.WrongEtagError(etag, old_item.hash)
            entry.delete()
        except etesync.exceptions.DoesNotExist as e:
            raise exceptions.NotFoundError(e)

    @contextlib.contextmanager
    def at_once(self):
        self._sync_journal()
        self._at_once = True
        try:
            yield self
            self._sync_journal()
        finally:
            self._at_once = False


class EtesyncContacts(EtesyncStorage):
    _collection_type = AddressBook
    _item_type = Contact
    storage_name = "etesync_contacts"


class EtesyncCalendars(EtesyncStorage):
    _collection_type = Calendar
    _item_type = Event
    storage_name = "etesync_calendars"
