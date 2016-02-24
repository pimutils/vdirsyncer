=========================
Full configuration manual
=========================

Vdirsyncer uses an ini-like format for storing its configuration. All values
are JSON, invalid JSON will get interpreted as string::

    x = "foo"  # String
    x = foo  # Shorthand for same string

    x = 42  # Integer

    x = ["a", "b", "c"]  # List of strings

    x = true  # Boolean
    x = false

    x = null  # Also known as None


.. _general_config:

General Section
===============

::

    [general]
    status_path = ...
    #password_command =


- ``status_path``: A directory where vdirsyncer will store some additional data
  for the next sync.

  The data is needed to determine whether a new item means it has been added on
  one side or deleted on the other. Relative paths will be interpreted as
  relative to the configuration file's directory.

  See `A simple synchronization algorithm
  <https://unterwaditzer.net/2016/sync-algorithm.html>`_ for what exactly is in
  there.

.. _pair_config:

Pair Section
============

::

    [pair pair_name]
    a = ...
    b = ...
    #collections = null
    #conflict_resolution = null

- Pair names can consist of any alphanumeric characters and the underscore.

- ``a`` and ``b`` reference the storages to sync by their names.

- ``collections``: A list of collections to synchronize when
  ``vdirsyncer sync`` is executed.

  The special values ``"from a"`` and ``"from b"``, tell vdirsyncer to try
  autodiscovery on a specific storage.

  Examples:

  - ``collections = ["from b", "foo", "bar"]`` makes vdirsyncer synchronize the
    collections from side B, and also the collections named "foo" and "bar".

  - ``collections = ["from b", from a"]`` makes vdirsyncer synchronize all
    existing collections on either side.

- ``conflict_resolution``: Optional, define how conflicts should be handled.  A
  conflict occurs when one item (event, task) changed on both sides since the
  last sync.

  Valid values are:

  - ``"a wins"`` and ``"b wins"``, where the whole item is taken from one side.
    Vdirsyncer will not attempt to merge the two items.
  - ``null``, the default, where an error is shown and no changes are done.

- ``metadata``: Metadata keys that should be synchronized when ``vdirsyncer
  metasync`` is executed. Example::

      metadata = ["color", "displayname"]

   This synchronizes the ``color`` and the ``displayname`` properties. The
   ``conflict_resolution`` parameter applies here as well.

.. _storage_config:

Storage Section
===============

::

    [storage storage_name]
    type = ...

- Storage names can consist of any alphanumeric characters and the underscore.

- ``type`` defines which kind of storage is defined. See :ref:`storages`.

- ``read_only`` defines whether the storage should be regarded as a read-only
  storage. The value ``true`` means synchronization will discard any changes
  made to the other side. The value ``false`` implies normal 2-way
  synchronization.

- Any further parameters are passed on to the storage class.

.. _storages:

Supported Storages
------------------

Read-write storages
~~~~~~~~~~~~~~~~~~~

These storages generally support reading and changing of their items. Their
default value for ``read_only`` is ``false``, but can be set to ``true`` if
wished.

CalDAV and CardDAV
++++++++++++++++++

.. autostorage:: vdirsyncer.storage.dav.CaldavStorage

.. autostorage:: vdirsyncer.storage.dav.CarddavStorage

remoteStorage
+++++++++++++

`remoteStorage <https://remotestorage.io/>`_ is an open per-user data storage
protocol. Vdirsyncer contains **highly experimental support** for it.

.. note::

    Do not use this storage if you're not prepared for data-loss and breakage.

To use them, you need to install some optional dependencies with::

    pip install vdirsyncer[remotestorage]

.. autostorage:: vdirsyncer.storage.remotestorage.RemoteStorageContacts

.. autostorage:: vdirsyncer.storage.remotestorage.RemoteStorageCalendars

Local
+++++

.. autostorage:: vdirsyncer.storage.filesystem.FilesystemStorage

.. autostorage:: vdirsyncer.storage.singlefile.SingleFileStorage


Read-only storages
~~~~~~~~~~~~~~~~~~

These storages don't support writing of their items, consequently ``read_only``
is set to ``true`` by default. Changing ``read_only`` to ``false`` on them
leads to an error.

.. autostorage:: vdirsyncer.storage.http.HttpStorage
