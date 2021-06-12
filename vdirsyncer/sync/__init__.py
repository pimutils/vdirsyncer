"""
The `sync` function in `vdirsyncer.sync` can be called on two instances of
`Storage` to synchronize them. Apart from the defined errors, this is the only
public API of this module.

The algorithm is based on the blogpost "How OfflineIMAP works" by Edward Z.
Yang: http://blog.ezyang.com/2012/08/how-offlineimap-works/

Some modifications to it are explained in
https://unterwaditzer.net/2016/sync-algorithm.html
"""
import contextlib
import itertools
import logging

from ..exceptions import UserError
from ..utils import uniq
from .exceptions import BothReadOnly
from .exceptions import IdentAlreadyExists
from .exceptions import PartialSync
from .exceptions import StorageEmpty
from .exceptions import SyncConflict
from .status import ItemMetadata
from .status import SubStatus

sync_logger = logging.getLogger(__name__)


class _StorageInfo:
    """A wrapper class that holds prefetched items, the status and other
    things."""

    def __init__(self, storage, status):
        self.storage = storage
        self.status = status
        self._item_cache = {}

    def prepare_new_status(self):
        storage_nonempty = False
        prefetch = []

        def _store_props(ident, props):
            try:
                self.status.insert_ident(ident, props)
            except IdentAlreadyExists as e:
                raise e.to_ident_conflict(self.storage)

        for href, etag in self.storage.list():
            storage_nonempty = True
            ident, meta = self.status.get_by_href(href)

            if meta is None or meta.href != href or meta.etag != etag:
                # Either the item is completely new, or updated
                # In both cases we should prefetch
                prefetch.append(href)
            else:
                # Metadata is completely identical
                _store_props(ident, meta)

        # Prefetch items
        for href, item, etag in self.storage.get_multi(prefetch) if prefetch else ():
            _store_props(item.ident, ItemMetadata(href=href, hash=item.hash, etag=etag))
            self.set_item_cache(item.ident, item)

        return storage_nonempty

    def is_changed(self, ident):
        old_meta = self.status.get(ident)
        if old_meta is None:  # new item
            return True

        new_meta = self.status.get_new(ident)

        return (
            new_meta.etag != old_meta.etag  # etag changed
            # item actually changed
            and (old_meta.hash is None or new_meta.hash != old_meta.hash)
        )

    def set_item_cache(self, ident, item):
        actual_hash = self.status.get_new(ident).hash
        assert actual_hash == item.hash
        self._item_cache[ident] = item

    def get_item_cache(self, ident):
        return self._item_cache[ident]


def sync(
    storage_a,
    storage_b,
    status,
    conflict_resolution=None,
    force_delete=False,
    error_callback=None,
    partial_sync="revert",
):
    """Synchronizes two storages.

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
    """
    if storage_a.read_only and storage_b.read_only:
        raise BothReadOnly()

    if conflict_resolution == "a wins":
        conflict_resolution = lambda a, b: a  # noqa: E731
    elif conflict_resolution == "b wins":
        conflict_resolution = lambda a, b: b  # noqa: E731

    status_nonempty = bool(next(status.iter_old(), None))

    with status.transaction():
        a_info = _StorageInfo(storage_a, SubStatus(status, "a"))
        b_info = _StorageInfo(storage_b, SubStatus(status, "b"))

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
                    action.run(a_info, b_info, conflict_resolution, partial_sync)
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
                if partial_sync == "error":
                    raise PartialSync(self.dest.storage)
                elif partial_sync == "ignore":
                    self.rollback(a, b)
                    return
                else:
                    assert partial_sync == "revert"

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
            sync_logger.info(
                "Copying (uploading) item {} to {}".format(
                    self.ident, self.dest.storage
                )
            )
            href, etag = self.dest.storage.upload(self.item)
            assert href is not None

        self.dest.status.insert_ident(
            self.ident, ItemMetadata(href=href, hash=self.item.hash, etag=etag)
        )


class Update(Action):
    def __init__(self, item, dest):
        self.item = item
        self.ident = item.ident
        self.dest = dest

    def _run_impl(self, a, b):
        if self.dest.storage.read_only:
            meta = ItemMetadata(hash=self.item.hash)
        else:
            sync_logger.info(
                "Copying (updating) item {} to {}".format(self.ident, self.dest.storage)
            )
            meta = self.dest.status.get_new(self.ident)
            meta.etag = self.dest.storage.update(meta.href, self.item, meta.etag)

        self.dest.status.update_ident(self.ident, meta)


class Delete(Action):
    def __init__(self, ident, dest):
        self.ident = ident
        self.dest = dest

    def _run_impl(self, a, b):
        meta = self.dest.status.get_new(self.ident)
        if not self.dest.storage.read_only:
            sync_logger.info(
                "Deleting item {} from {}".format(self.ident, self.dest.storage)
            )
            self.dest.storage.delete(meta.href, meta.etag)

        self.dest.status.remove_ident(self.ident)


class ResolveConflict(Action):
    def __init__(self, ident):
        self.ident = ident

    def run(self, a, b, conflict_resolution, partial_sync):
        with self.auto_rollback(a, b):
            sync_logger.info(
                "Doing conflict resolution for item {}...".format(self.ident)
            )

            meta_a = a.status.get_new(self.ident)
            meta_b = b.status.get_new(self.ident)

            if meta_a.hash == meta_b.hash:
                sync_logger.info("...same content on both sides.")
            elif conflict_resolution is None:
                raise SyncConflict(
                    ident=self.ident, href_a=meta_a.href, href_b=meta_b.href
                )
            elif callable(conflict_resolution):
                item_a = a.get_item_cache(self.ident)
                item_b = b.get_item_cache(self.ident)
                new_item = conflict_resolution(item_a, item_b)
                if new_item.hash != meta_a.hash:
                    Update(new_item, a).run(a, b, conflict_resolution, partial_sync)
                if new_item.hash != meta_b.hash:
                    Update(new_item, b).run(a, b, conflict_resolution, partial_sync)
            else:
                raise UserError(
                    "Invalid conflict resolution mode: {!r}".format(conflict_resolution)
                )


def _get_actions(a_info, b_info):
    for ident in uniq(
        itertools.chain(
            a_info.status.parent.iter_new(), a_info.status.parent.iter_old()
        )
    ):
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
