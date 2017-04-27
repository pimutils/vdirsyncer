# -*- coding: utf-8 -*-
'''
The function in `vdirsyncer.sync` can be called on two instances of `Storage`
to synchronize them. Due to the abstract API storage classes are implementing,
the two given instances don't have to be of the same exact type. This allows us
not only to synchronize a local vdir with a CalDAV server, but also synchronize
two CalDAV servers or two local vdirs.

The algorithm is based on the blogpost "How OfflineIMAP works" by Edward Z.
Yang: http://blog.ezyang.com/2012/08/how-offlineimap-works/

Some modifications to it are explained in
https://unterwaditzer.net/2016/sync-algorithm.html
'''
import abc
import contextlib
import itertools
import logging
import sqlite3
import sys

from . import exceptions
from .utils import uniq

sync_logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _exclusive_transaction(conn):
    c = None
    try:
        c = conn.execute('BEGIN EXCLUSIVE TRANSACTION')
        yield c
        c.execute('COMMIT')
    except BaseException:
        if c is None:
            raise
        _, e, tb = sys.exc_info()
        c.execute('ROLLBACK')
        raise e.with_traceback(tb)


class SyncError(exceptions.Error):
    '''Errors related to synchronization.'''


class SyncConflict(SyncError):
    '''
    Two items changed since the last sync, they now have different contents and
    no conflict resolution method was given.

    :param ident: The ident of the item.
    :param href_a: The item's href on side A.
    :param href_b: The item's href on side B.
    '''

    ident = None
    href_a = None
    href_b = None


class IdentConflict(SyncError):
    '''
    Multiple items on the same storage have the same UID.

    :param storage: The affected storage.
    :param hrefs: List of affected hrefs on `storage`.
    '''
    storage = None
    _hrefs = None

    @property
    def hrefs(self):
        return self._hrefs

    @hrefs.setter
    def hrefs(self, val):
        new_val = set(val)
        assert len(new_val) > 1, val
        self._hrefs = new_val


class StorageEmpty(SyncError):
    '''
    One storage unexpectedly got completely empty between two synchronizations.
    The first argument is the empty storage.

    :param empty_storage: The empty
        :py:class:`vdirsyncer.storage.base.Storage`.
    '''

    empty_storage = None


class BothReadOnly(SyncError):
    '''
    Both storages are marked as read-only. Synchronization is therefore not
    possible.
    '''


class PartialSync(SyncError):
    '''
    Attempted change on read-only storage.
    '''
    storage = None


class _IdentAlreadyExists(SyncError):
    '''Like IdentConflict, but for internal state. If this bubbles up, we don't
    have a data race, but a bug.'''
    old_href = None
    new_href = None

    def to_ident_conflict(self, storage):
        return IdentConflict(storage=storage,
                             hrefs=[self.old_href, self.new_href])


class _StatusBase(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def transaction(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def insert_ident_a(self, ident, props):
        raise NotImplementedError()

    @abc.abstractmethod
    def insert_ident_b(self, ident, props):
        raise NotImplementedError()

    @abc.abstractmethod
    def update_ident_a(self, ident, props):
        raise NotImplementedError()

    @abc.abstractmethod
    def update_ident_b(self, ident, props):
        raise NotImplementedError()

    @abc.abstractmethod
    def remove_ident(self, ident):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_a(self, ident):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_b(self, ident):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_new_a(self, ident):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_new_b(self, ident):
        raise NotImplementedError()

    @abc.abstractmethod
    def iter_old(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def iter_new(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_by_href_a(self, href, default=(None, None)):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_by_href_b(self, href, default=(None, None)):
        raise NotImplementedError()

    @abc.abstractmethod
    def rollback(self, ident):
        raise NotImplementedError()


class SqliteStatus(_StatusBase):
    SCHEMA_VERSION = 1

    def __init__(self, path):
        self._path = path
        self._c = sqlite3.connect(path)
        self._c.isolation_level = None  # turn off idiocy of DB-API
        self._c.row_factory = sqlite3.Row
        self._update_schema()

    def load_legacy_status(self, status):
        for ident, metadata in status.items():
            if len(metadata) == 4:
                href_a, etag_a, href_b, etag_b = metadata
                params = (ident, href_a, 'UNDEFINED', etag_a, href_b,
                          'UNDEFINED', etag_b)
            else:
                a, b = metadata
                params = (ident,
                          a.get('href'), a.get('hash', 'UNDEFINED'),
                          a.get('etag'),
                          b.get('href'), b.get('hash', 'UNDEFINED'),
                          b.get('etag'))

            self._c.execute(
                'INSERT INTO status'
                ' (ident, href_a, hash_a, etag_a,'
                '  href_b, hash_b, etag_b)'
                ' VALUES (?, ?, ?, ?, ?, ?, ?)',
                params
            )

    def to_legacy_status(self):
        for ident in self.iter_old():
            a = self.get_a(ident)
            b = self.get_b(ident)
            yield ident, (a.to_status(), b.to_status())

    def _update_schema(self):
        if self._is_latest_version():
            return

        # If we ever bump the schema version, we will need a way to migrate
        # data.
        with _exclusive_transaction(self._c) as c:
            c.execute('CREATE TABLE meta ( "version" INTEGER PRIMARY KEY )')
            c.execute('INSERT INTO meta (version) VALUES (?)',
                      (self.SCHEMA_VERSION,))

            # I know that this is a bad schema, but right there is just too
            # little gain in deduplicating the .._a and .._b columns.
            c.execute('''CREATE TABLE status (
                "ident" TEXT PRIMARY KEY NOT NULL,
                "href_a" TEXT,
                "href_b" TEXT,
                "hash_a" TEXT NOT NULL,
                "hash_b" TEXT NOT NULL,
                "etag_a" TEXT,
                "etag_b" TEXT
            ); ''')
            c.execute('CREATE UNIQUE INDEX by_href_a ON status(href_a)')
            c.execute('CREATE UNIQUE INDEX by_href_b ON status(href_b)')

            # We cannot add NOT NULL here because data is first fetched for the
            # storage a, then storage b. Inbetween the `_b`-columns are filled
            # with NULL.
            #
            # In an ideal world we would be able to start a transaction with
            # one cursor, write our new data into status and simultaneously
            # query the old status data using a different cursor.
            # Unfortunately sqlite enforces NOT NULL constraints immediately,
            # not just at commit. Since there is also no way to alter
            # constraints on a table (disable constraints on start of
            # transaction and reenable on end), it's a separate table now that
            # just gets copied over before we commit.  That's a lot of copying,
            # sadly.
            c.execute('''CREATE TABLE new_status (
                "ident" TEXT PRIMARY KEY NOT NULL,
                "href_a" TEXT,
                "href_b" TEXT,
                "hash_a" TEXT,
                "hash_b" TEXT,
                "etag_a" TEXT,
                "etag_b" TEXT
            ); ''')

    def _is_latest_version(self):
        try:
            return bool(self._c.execute(
                'SELECT version FROM meta WHERE version = ?',
                (self.SCHEMA_VERSION,)
            ).fetchone())
        except sqlite3.OperationalError:
            return False

    @contextlib.contextmanager
    def transaction(self):
        old_c = self._c
        try:
            with _exclusive_transaction(self._c) as new_c:
                self._c = new_c
                yield
                self._c.execute('DELETE FROM status')
                self._c.execute('INSERT INTO status '
                                'SELECT * FROM new_status')
                self._c.execute('DELETE FROM new_status')
        finally:
            self._c = old_c

    def insert_ident_a(self, ident, a_props):
        # FIXME: Super inefficient
        old_props = self.get_new_a(ident)
        if old_props is not None:
            raise _IdentAlreadyExists(old_href=old_props.href,
                                      new_href=a_props.href)
        b_props = self.get_new_b(ident) or _ItemMetadata()
        self._c.execute(
            'INSERT OR REPLACE INTO new_status '
            'VALUES(?, ?, ?, ?, ?, ?, ?)',
            (ident, a_props.href, b_props.href, a_props.hash, b_props.hash,
             a_props.etag, b_props.etag)
        )

    def insert_ident_b(self, ident, b_props):
        # FIXME: Super inefficient
        old_props = self.get_new_b(ident)
        if old_props is not None:
            raise _IdentAlreadyExists(old_href=old_props.href,
                                      new_href=b_props.href)
        a_props = self.get_new_a(ident) or _ItemMetadata()
        self._c.execute(
            'INSERT OR REPLACE INTO new_status '
            'VALUES(?, ?, ?, ?, ?, ?, ?)',
            (ident, a_props.href, b_props.href, a_props.hash, b_props.hash,
             a_props.etag, b_props.etag)
        )

    def update_ident_a(self, ident, props):
        self._c.execute(
            'UPDATE new_status'
            ' SET href_a=?, hash_a=?, etag_a=?'
            ' WHERE ident=?',
            (props.href, props.hash, props.etag, ident)
        )
        assert self._c.rowcount > 0

    def update_ident_b(self, ident, props):
        self._c.execute(
            'UPDATE new_status'
            ' SET href_b=?, hash_b=?, etag_b=?'
            ' WHERE ident=?',
            (props.href, props.hash, props.etag, ident)
        )
        assert self._c.rowcount > 0

    def remove_ident(self, ident):
        self._c.execute('DELETE FROM new_status WHERE ident=?', (ident,))

    def _get_impl(self, ident, side, table):
        res = self._c.execute('SELECT href_{side} AS href,'
                              '       hash_{side} AS hash,'
                              '       etag_{side} AS etag '
                              'FROM {table} WHERE ident=?'
                              .format(side=side, table=table),
                              (ident,)).fetchone()
        if res is None:
            return None

        if res['hash'] is None:  # FIXME: Implement as constraint in db
            assert res['href'] is None
            assert res['etag'] is None
            return None

        res = dict(res)
        return _ItemMetadata(**res)

    def get_a(self, ident):
        return self._get_impl(ident, side='a', table='status')

    def get_b(self, ident):
        return self._get_impl(ident, side='b', table='status')

    def get_new_a(self, ident):
        return self._get_impl(ident, side='a', table='new_status')

    def get_new_b(self, ident):
        return self._get_impl(ident, side='b', table='new_status')

    def iter_old(self):
        return iter(res['ident'] for res in
                    self._c.execute('SELECT ident FROM status').fetchall())

    def iter_new(self):
        return iter(res['ident'] for res in
                    self._c.execute('SELECT ident FROM new_status').fetchall())

    def rollback(self, ident):
        a = self.get_a(ident)
        b = self.get_b(ident)
        assert (a is None) == (b is None)

        if a is None and b is None:
            self.remove_ident(ident)
            return

        self._c.execute(
            'INSERT OR REPLACE INTO new_status'
            ' VALUES (?, ?, ?, ?, ?, ?, ?)',
            (ident, a.href, b.href, a.hash, b.hash, a.etag, b.etag)
        )

    def _get_by_href_impl(self, href, default=(None, None), side=None):
        res = self._c.execute(
            'SELECT ident, hash_{side} AS hash, etag_{side} AS etag '
            'FROM status WHERE href_{side}=?'.format(side=side),
            (href,)).fetchone()
        if not res:
            return default
        return res['ident'], _ItemMetadata(
            href=href,
            hash=res['hash'],
            etag=res['etag'],
        )

    def get_by_href_a(self, *a, **kw):
        kw['side'] = 'a'
        return self._get_by_href_impl(*a, **kw)

    def get_by_href_b(self, *a, **kw):
        kw['side'] = 'b'
        return self._get_by_href_impl(*a, **kw)


class _SubStatus(object):
    def __init__(self, parent, side):
        self.parent = parent
        assert side in 'ab'

        self.remove_ident = parent.remove_ident

        if side == 'a':
            self.insert_ident = parent.insert_ident_a
            self.update_ident = parent.update_ident_a
            self.get = parent.get_a
            self.get_new = parent.get_new_a
            self.get_by_href = parent.get_by_href_a
        else:
            self.insert_ident = parent.insert_ident_b
            self.update_ident = parent.update_ident_b
            self.get = parent.get_b
            self.get_new = parent.get_new_b
            self.get_by_href = parent.get_by_href_b


class _ItemMetadata:
    href = None
    hash = None
    etag = None

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            assert hasattr(self, k)
            setattr(self, k, v)

    def to_status(self):
        return {
            'href': self.href,
            'etag': self.etag,
            'hash': self.hash
        }


class _StorageInfo(object):
    '''A wrapper class that holds prefetched items, the status and other
    things.'''
    def __init__(self, storage, status):
        self.storage = storage
        self.status = status
        self._item_cache = {}

    def prepare_new_status(self):
        storage_nonempty = False
        prefetch = []

        def _store_props(ident, props):
            nonlocal storage_nonempty
            storage_nonempty = True

            try:
                self.status.insert_ident(ident, props)
            except _IdentAlreadyExists as e:
                raise e.to_ident_conflict(self.storage)

        for href, etag in self.storage.list():
            ident, meta = self.status.get_by_href(href)
            if meta is None or meta.href != href or meta.etag != etag:
                # Either the item is completely new, or updated
                # In both cases we should prefetch
                prefetch.append(href)
            else:
                # Metadata is completely identical
                _store_props(ident, meta)

        # Prefetch items
        for href, item, etag in (self.storage.get_multi(prefetch)
                                 if prefetch else ()):
            _store_props(item.ident, _ItemMetadata(
                href=href,
                hash=item.hash,
                etag=etag
            ))
            self.set_item_cache(item.ident, item)

        return storage_nonempty

    def is_changed(self, ident):
        old_meta = self.status.get(ident)
        if old_meta is None:  # new item
            return True

        new_meta = self.status.get_new(ident)

        return (
            new_meta.etag != old_meta.etag and  # etag changed
            # item actually changed
            (old_meta.hash is None or new_meta.hash != old_meta.hash)
        )

    def set_item_cache(self, ident, item):
        actual_hash = self.status.get_new(ident).hash
        assert actual_hash == item.hash
        self._item_cache[ident] = item

    def get_item_cache(self, ident):
        return self._item_cache[ident]


def sync(storage_a, storage_b, status, conflict_resolution=None,
         force_delete=False, error_callback=None, partial_sync='revert'):
    '''Synchronizes two storages.

    :param storage_a: The first storage
    :type storage_a: :class:`vdirsyncer.storage.base.Storage`
    :param storage_b: The second storage
    :type storage_b: :class:`vdirsyncer.storage.base.Storage`
    :param status: {ident: (href_a, etag_a, href_b, etag_b)}
        metadata about the two storages for detection of changes. Will be
        modified by the function and should be passed to it at the next sync.
        If this is the first sync, an empty dictionary should be provided.
    :param conflict_resolution: A function that, given two conflicting item
        versions A and B, returns a new item with conflicts resolved. The UID
        must be the same. The strings `"a wins"` and `"b wins"` are also
        accepted to mean that side's version will always be taken. If none
        is provided, the sync function will raise :py:exc:`SyncConflict`.
    :param force_delete: When one storage got completely emptied between two
        syncs, :py:exc:`StorageEmpty` is raised for
        safety. Setting this parameter to ``True`` disables this safety
        measure.
    :param error_callback: Instead of raising errors when executing actions,
        call the given function with an `Exception` as the only argument.
    :param partial_sync: What to do when doing sync actions on read-only
        storages.

        - ``error``: Raise an error.
        - ``ignore``: Those actions are simply skipped.
        - ``revert`` (default): Revert changes on other side.
    '''
    if storage_a.read_only and storage_b.read_only:
        raise BothReadOnly()

    if conflict_resolution == 'a wins':
        conflict_resolution = lambda a, b: a
    elif conflict_resolution == 'b wins':
        conflict_resolution = lambda a, b: b

    status_nonempty = bool(next(status.iter_old(), None))

    with status.transaction():
        a_info = _StorageInfo(storage_a, _SubStatus(status, 'a'))
        b_info = _StorageInfo(storage_b, _SubStatus(status, 'b'))

        a_nonempty = a_info.prepare_new_status()
        b_nonempty = b_info.prepare_new_status()

        if status_nonempty and not force_delete:
            if a_nonempty and not b_nonempty:
                raise StorageEmpty(empty_storage=storage_b)
            elif not a_nonempty and b_nonempty:
                raise StorageEmpty(empty_storage=storage_a)

        actions = list(_get_actions(a_info, b_info))

        with storage_a.at_once(), storage_b.at_once():
            for action in actions:
                try:
                    action.run(
                        a_info,
                        b_info,
                        conflict_resolution,
                        partial_sync
                    )
                except Exception as e:
                    if error_callback:
                        error_callback(e)
                    else:
                        raise


class Action:
    def _run_impl(self, a, b):  # pragma: no cover
        raise NotImplementedError()

    def run(self, a, b, conflict_resolution, partial_sync):
        with self.auto_rollback(a, b):
            if self.dest.storage.read_only:
                if partial_sync == 'error':
                    raise PartialSync(self.dest.storage)
                elif partial_sync == 'ignore':
                    self.rollback(a, b)
                    return
                else:
                    assert partial_sync == 'revert'

            self._run_impl(a, b)

    @contextlib.contextmanager
    def auto_rollback(self, a, b):
        try:
            yield
        except BaseException as e:
            self.rollback(a, b)
            raise e

    def rollback(self, a, b):
        a.status.parent.rollback(self.ident)


class Upload(Action):
    def __init__(self, item, dest):
        self.item = item
        self.ident = item.ident
        self.dest = dest

    def _run_impl(self, a, b):

        if self.dest.storage.read_only:
            href = etag = None
        else:
            sync_logger.info(u'Copying (uploading) item {} to {}'
                             .format(self.ident, self.dest.storage))
            href, etag = self.dest.storage.upload(self.item)
            assert href is not None

        self.dest.status.insert_ident(self.ident, _ItemMetadata(
            href=href,
            hash=self.item.hash,
            etag=etag
        ))


class Update(Action):
    def __init__(self, item, dest):
        self.item = item
        self.ident = item.ident
        self.dest = dest

    def _run_impl(self, a, b):
        if self.dest.storage.read_only:
            meta = _ItemMetadata(hash=self.item.hash)
        else:
            sync_logger.info(u'Copying (updating) item {} to {}'
                             .format(self.ident, self.dest.storage))
            meta = self.dest.status.get_new(self.ident)
            meta.etag = \
                self.dest.storage.update(meta.href, self.item, meta.etag)

        self.dest.status.update_ident(self.ident, meta)


class Delete(Action):
    def __init__(self, ident, dest):
        self.ident = ident
        self.dest = dest

    def _run_impl(self, a, b):
        meta = self.dest.status.get_new(self.ident)
        if not self.dest.storage.read_only:
            sync_logger.info(u'Deleting item {} from {}'
                             .format(self.ident, self.dest.storage))
            self.dest.storage.delete(meta.href, meta.etag)

        self.dest.status.remove_ident(self.ident)


class ResolveConflict(Action):
    def __init__(self, ident):
        self.ident = ident

    def run(self, a, b, conflict_resolution, partial_sync):
        with self.auto_rollback(a, b):
            sync_logger.info(u'Doing conflict resolution for item {}...'
                             .format(self.ident))

            meta_a = a.status.get_new(self.ident)
            meta_b = b.status.get_new(self.ident)

            if meta_a.hash == meta_b.hash:
                sync_logger.info(u'...same content on both sides.')
            elif conflict_resolution is None:
                raise SyncConflict(ident=self.ident, href_a=meta_a.href,
                                   href_b=meta_b.href)
            elif callable(conflict_resolution):
                item_a = a.get_item_cache(self.ident)
                item_b = b.get_item_cache(self.ident)
                new_item = conflict_resolution(item_a, item_b)
                if new_item.hash != meta_a.hash:
                    Update(new_item, a).run(a, b, conflict_resolution,
                                            partial_sync)
                if new_item.hash != meta_b.hash:
                    Update(new_item, b).run(a, b, conflict_resolution,
                                            partial_sync)
            else:
                raise exceptions.UserError(
                    'Invalid conflict resolution mode: {!r}'
                    .format(conflict_resolution))


def _get_actions(a_info, b_info):
    for ident in uniq(itertools.chain(a_info.status.parent.iter_new(),
                                      a_info.status.parent.iter_old())):
        a = a_info.status.get_new(ident)
        b = b_info.status.get_new(ident)

        if a and b:
            a_changed = a_info.is_changed(ident)
            b_changed = b_info.is_changed(ident)
            if a_changed and b_changed:
                # item was modified on both sides
                # OR: missing status
                yield ResolveConflict(ident)
            elif a_changed and not b_changed:
                # item was only modified in a
                yield Update(a_info.get_item_cache(ident), b_info)
            elif not a_changed and b_changed:
                # item was only modified in b
                yield Update(b_info.get_item_cache(ident), a_info)
        elif a and not b:
            if a_info.is_changed(ident):
                # was deleted from b but modified on a
                # OR: new item was created in a
                yield Upload(a_info.get_item_cache(ident), b_info)
            else:
                # was deleted from b and not modified on a
                yield Delete(ident, a_info)
        elif not a and b:
            if b_info.is_changed(ident):
                # was deleted from a but modified on b
                # OR: new item was created in b
                yield Upload(b_info.get_item_cache(ident), a_info)
            else:
                # was deleted from a and not changed on b
                yield Delete(ident, b_info)
