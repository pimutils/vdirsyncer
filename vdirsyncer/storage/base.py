import contextlib
import functools

from .. import exceptions
from ..utils import uniq


def mutating_storage_method(f):
    @functools.wraps(f)
    def inner(self, *args, **kwargs):
        if self.read_only:
            raise exceptions.ReadOnlyError("This storage is read-only.")
        return f(self, *args, **kwargs)

    return inner


class StorageMeta(type):
    def __init__(cls, name, bases, d):
        for method in ("update", "upload", "delete"):
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
    storage_name = None

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
    _repr_attributes = ()

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
    def discover(cls, **kwargs):
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
        raise NotImplementedError()

    @classmethod
    def create_collection(cls, collection, **kwargs):
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

    def list(self):
        """
        :returns: list of (href, etag)
        """
        raise NotImplementedError()

    def get(self, href):
        """Fetch a single item.

        :param href: href to fetch
        :returns: (item, etag)
        :raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` if item can't
            be found.
        """
        raise NotImplementedError()

    def get_multi(self, hrefs):
        """Fetch multiple items. Duplicate hrefs must be ignored.

        Functionally similar to :py:meth:`get`, but might bring performance
        benefits on some storages when used cleverly.

        :param hrefs: list of hrefs to fetch
        :raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` if one of the
            items couldn't be found.
        :returns: iterable of (href, item, etag)
        """
        for href in uniq(hrefs):
            item, etag = self.get(href)
            yield href, item, etag

    def has(self, href):
        """Check if an item exists by its href.

        :returns: True or False
        """
        try:
            self.get(href)
        except exceptions.PreconditionFailed:
            return False
        else:
            return True

    def upload(self, item):
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

    def update(self, href, item, etag):
        """Update an item.

        The etag may be none in some cases, see `upload`.

        :raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` if the etag on
            the server doesn't match the given etag or if the item doesn't
            exist.

        :returns: etag
        """
        raise NotImplementedError()

    def delete(self, href, etag):
        """Delete an item by href.

        :raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` when item has
            a different etag or doesn't exist.
        """
        raise NotImplementedError()

    @contextlib.contextmanager
    def at_once(self):
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

    def get_meta(self, key):
        """Get metadata value for collection/storage.

        See the vdir specification for the keys that *have* to be accepted.

        :param key: The metadata key.
        :type key: unicode
        """

        raise NotImplementedError("This storage does not support metadata.")

    def set_meta(self, key, value):
        """Get metadata value for collection/storage.

        :param key: The metadata key.
        :type key: unicode
        :param value: The value.
        :type value: unicode
        """

        raise NotImplementedError("This storage does not support metadata.")


def normalize_meta_value(value):
    # `None` is returned by iCloud for empty properties.
    if not value or value == "None":
        value = ""
    return value.strip()
