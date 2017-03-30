import logging
import os

import atomicwrites
import click
from pyetesync import api as etesync

from ..cli.utils import assert_permissions
from ..utils import checkdir
from ..vobject import Item

from .base import Storage


logger = logging.getLogger(__name__)


class _Session:
    def __init__(self, email, secrets_dir, server_url=None):
        server_url = server_url or etesync.API_URL
        self.email = email
        self.secrets_dir = os.path.join(secrets_dir, email + '/')

        self._auth_token_path = os.path.join(self.secrets_dir, 'auth_token')
        self._key_path = os.path.join(self.secrets_dir, 'key')

        auth_token = self._get_auth_token()
        if not auth_token:
            password = click.prompt('Enter service password for {}'
                                    .format(self.email), hide_input=True)
            auth_token = etesync.Authenticator(server_url) \
                .get_auth_token(self.email, password)
            self._set_auth_token(auth_token)

        self.etesync = etesync.EteSync(email, auth_token, remote=server_url)

        key = self._get_key()
        if not key:
            password = click.prompt('Enter key password', hide_input=True)
            click.echo('Deriving key for {}'.format(self.email))
            self.etesync.derive_key(password)
            self._set_key(self.etesync.cipher_key)
        else:
            self.etesync.cipher_key = key

    def _get_auth_token(self):
        try:
            with open(self._auth_token_path) as f:
                return f.read().strip() or None
        except (OSError, IOError):
            pass

    def _set_auth_token(self, token):
        checkdir(os.path.dirname(self._auth_token_path), create=True)
        with atomicwrites.atomic_write(self._auth_token_path) as f:
            f.write(token)
        assert_permissions(self._auth_token_path, 0o600)

    def _get_key(self):
        try:
            with open(self._key_path, 'rb') as f:
                return f.read()
        except (OSError, IOError):
            pass

    def _set_key(self, content):
        checkdir(os.path.dirname(self._key_path), create=True)
        with atomicwrites.atomic_write(self._key_path, mode='wb') as f:
            f.write(content)
        assert_permissions(self._key_path, 0o600)


class EtesyncStorage(Storage):
    _collection_type = None

    read_only = True

    def __init__(self, email, secrets_dir, server_url=None, **kwargs):
        if kwargs.get('collection', None) is None:
            raise ValueError('Collection argument required')

        self._session = _Session(email, secrets_dir, server_url)
        self._items_cache = {}  # XXX: Slow
        super(EtesyncStorage, self).__init__(**kwargs)

    @classmethod
    def discover(cls, email, secrets_dir, server_url=None, **kwargs):
        assert cls._collection_type
        session = _Session(email, secrets_dir, server_url)
        session.etesync.sync_journal_list()
        for entry in session.etesync.list():
            if isinstance(entry.collection, cls._collection_type):
                yield dict(
                    email=email,
                    secrets_dir=secrets_dir,
                    collection=entry.uid,
                    **kwargs
                )
            else:
                logger.debug('Skipping collection: {!r}'.format(entry))

    def list(self):
        self._session.etesync.sync_journal(self.collection)
        self._items_cache.clear()
        journal = self._session.etesync.get(self.collection)
        for entry in journal.list():
            self._items_cache[entry.uid] = item = \
                Item(entry.content.decode('utf-8'))
            yield entry.uid, item.hash

    def get(self, href):
        item = self._items_cache[href]
        return item, item.hash


class EtesyncContacts(EtesyncStorage):
    _collection_type = etesync.AddressBook
    storage_name = 'etesync_contacts'


class EtesyncCalendars(EtesyncStorage):
    _collection_type = etesync.Calendar
    storage_name = 'etesync_calendars'
