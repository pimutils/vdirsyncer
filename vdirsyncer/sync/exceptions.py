from .. import exceptions


class SyncError(exceptions.Error):
    """Errors related to synchronization."""


class SyncConflict(SyncError):
    """
    Two items changed since the last sync, they now have different contents and
    no conflict resolution method was given.

    :param ident: The ident of the item.
    :param href_a: The item's href on side A.
    :param href_b: The item's href on side B.
    """

    ident = None
    href_a = None
    href_b = None


class IdentConflict(SyncError):
    """
    Multiple items on the same storage have the same UID.

    :param storage: The affected storage.
    :param hrefs: List of affected hrefs on `storage`.
    """

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
    """
    One storage unexpectedly got completely empty between two synchronizations.
    The first argument is the empty storage.

    :param empty_storage: The empty
        :py:class:`vdirsyncer.storage.base.Storage`.
    """

    empty_storage = None


class BothReadOnly(SyncError):
    """
    Both storages are marked as read-only. Synchronization is therefore not
    possible.
    """


class PartialSync(SyncError):
    """
    Attempted change on read-only storage.
    """

    storage = None


class IdentAlreadyExists(SyncError):
    """Like IdentConflict, but for internal state. If this bubbles up, we don't
    have a data race, but a bug."""

    old_href = None
    new_href = None

    def to_ident_conflict(self, storage):
        return IdentConflict(storage=storage, hrefs=[self.old_href, self.new_href])
