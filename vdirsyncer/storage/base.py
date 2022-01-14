import contextlib
import functools
from abc import ABCMeta
from abc import abstractmethod
from typing import Iterable
from typing import List
from typing import Optional

from vdirsyncer.vobject import Item

from .. import exceptions
from ..utils import uniq


def mutating_storage_method(f):
    """Wrap a method and fail if the instance is readonly."""

    @functools.wraps(f)
    async def inner(self, *args, **kwargs):
        if self.read_only:
            raise exceptions.ReadOnlyError("This storage is read-only.")
        return await f(self, *args, **kwargs)

    return inner


class StorageMeta(ABCMeta):
    def __init__(cls, name, bases, d):
        """Wrap mutating methods to fail if the storage is readonly."""

        for method in ("update", "upload", "delete", "set_meta"):
            setattr(cls, method, mutating_storage_method(getattr(cls, method)))
        return super().__init__(name, bases, d)


class Storage(metaclass=StorageMeta):

    """Superclass of all storages, interface that all storages have to
    implement.

    Terminology:
      - ITEM: Instance of the Item class, represents a calendar event, task or
          contact.
      - HREF: String; Per-storage identifier of item, might be UID. The reason
          items aren't just referenced by their UID is because the CalDAV and
          CardDAV specifications make this unperformant to implement.
      - ETAG: String; Checksum of item, or something similar that changes when
          the item does.

    Strings can be either unicode strings or bytestrings. If bytestrings, an
    ASCII encoding is assumed.

    :param read_only: Whether the synchronization algorithm should avoid writes
        to this storage. Some storages accept no value other than ``True``.
    """

    fileext = ".txt"

    # The string used in the config to denote the type of storage. Should be
    # overridden by subclasses.
    storage_name: str

    # The string used in the config to denote a particular instance. Will be
    # overridden during instantiation.
    instance_name = None

    # The machine-readable name of this collection.
    collection = None

    # A value of True means the storage does not support write-methods such as
    # upload, update and delete.  A value of False means the storage does
    # support those methods.
    read_only = False

    # The attribute values to show in the representation of the storage.
    _repr_attributes: List[str] = []

    def __init__(self, instance_name=None, read_only=None, collection=None):
        if read_only is None:
            read_only = self.read_only
        if self.read_only and not read_only:
            raise exceptions.UserError("This storage can only be read-only.")
        self.read_only = bool(read_only)

        if collection and instance_name:
            instance_name = f"{instance_name}/{collection}"
        self.instance_name = instance_name
        self.collection = collection

    @classmethod
    async def discover(cls, **kwargs):
        """Discover collections given a basepath or -URL to many collections.

        :param **kwargs: Keyword arguments to additionally pass to the storage
            instances returned. You shouldn't pass `collection` here, otherwise
            TypeError will be raised.
        :returns: iterable of ``storage_args``.
            ``storage_args`` is a dictionary of ``**kwargs`` to pass to this
            class to obtain a storage instance pointing to this collection. It
            also must contain a ``"collection"`` key.  That key's value is used
            to match two collections together for synchronization. IOW it is a
            machine-readable identifier for the collection, usually obtained
            from the last segment of a URL or filesystem path.

        """
        if False:
            yield  # Needs to be an async generator
        raise NotImplementedError()

    @classmethod
    async def create_collection(cls, collection, **kwargs):
        """
        Create the specified collection and return the new arguments.

        ``collection=None`` means the arguments are already pointing to a
        possible collection location.

        The returned args should contain the collection name, for UI purposes.
        """
        raise NotImplementedError()

    def __repr__(self):
        try:
            if self.instance_name:
                return str(self.instance_name)
        except ValueError:
            pass

        return "<{}(**{})>".format(
            self.__class__.__name__,
            {x: getattr(self, x) for x in self._repr_attributes},
        )

    @abstractmethod
    async def list(self) -> List[tuple]:
        """
        :returns: list of (href, etag)
        """

    @abstractmethod
    async def get(self, href: str):
        """Fetch a single item.

        :param href: href to fetch
        :returns: (item, etag)
        :raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` if item can't
            be found.
        """

    async def get_multi(self, hrefs: Iterable[str]):
        """Fetch multiple items. Duplicate hrefs must be ignored.

        Functionally similar to :py:meth:`get`, but might bring performance
        benefits on some storages when used cleverly.

        :param hrefs: list of hrefs to fetch
        :raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` if one of the
            items couldn't be found.
        :returns: iterable of (href, item, etag)
        """
        for href in uniq(hrefs):
            item, etag = await self.get(href)
            yield href, item, etag

    async def has(self, href) -> bool:
        """Check if an item exists by its href."""
        try:
            await self.get(href)
        except exceptions.PreconditionFailed:
            return False
        else:
            return True

    async def upload(self, item: Item):
        """Upload a new item.

        In cases where the new etag cannot be atomically determined (i.e. in
        the same "transaction" as the upload itself), this method may return
        `None` as etag. This special case only exists because of DAV. Avoid
        this situation whenever possible.

        :raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` if there is
            already an item with that href.

        :returns: (href, etag)
        """
        raise NotImplementedError()

    async def update(self, href: str, item: Item, etag):
        """Update an item.

        The etag may be none in some cases, see `upload`.

        :raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` if the etag on
            the server doesn't match the given etag or if the item doesn't
            exist.

        :returns: etag
        """
        raise NotImplementedError()

    async def delete(self, href: str, etag: str):
        """Delete an item by href.

        :raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` when item has
            a different etag or doesn't exist.
        """
        raise NotImplementedError()

    @contextlib.asynccontextmanager
    async def at_once(self):
        """A contextmanager that buffers all writes.

        Essentially, this::

            s.upload(...)
            s.update(...)

        becomes this::

            with s.at_once():
                s.upload(...)
                s.update(...)

        Note that this removes guarantees about which exceptions are returned
        when.
        """
        yield

    async def get_meta(self, key: str) -> Optional[str]:
        """Get metadata value for collection/storage.

        See the vdir specification for the keys that *have* to be accepted.

        :param key: The metadata key.
        :return: The metadata or None, if metadata is missing.
        """
        raise NotImplementedError("This storage does not support metadata.")

    async def set_meta(self, key: str, value: Optional[str]):
        """Set metadata value for collection/storage.

        :param key: The metadata key.
        :param value: The value. Use None to delete the data.
        """
        raise NotImplementedError("This storage does not support metadata.")


def normalize_meta_value(value) -> Optional[str]:
    # `None` is returned by iCloud for empty properties.
    if value is None or value == "None":
        return None
    return value.strip() if value else ""
