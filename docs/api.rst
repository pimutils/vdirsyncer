===
API
===

Config Parameters
=================

.. _general_config:

General Section
---------------

::

    [general]
    status_path = ...
    #processes = 0


- ``status_path``: A directory where vdirsyncer will store metadata for the
  next sync. The data is needed to determine whether a new item means it has
  been added on one side or deleted on the other.

- ``processes``: Optional, defines the maximal amount of threads to use for
  syncing.  By default there is no limit, which means vdirsyncer will try to
  open a connection for each collection to be synced. The value ``0`` is
  ignored. Setting this to ``1`` will only synchronize one collection at a
  time.

  While this often greatly increases performance, you might have valid reasons
  to set this to a smaller number. For example, your DAV server running on a
  Raspberry Pi is so slow that multiple connections don't help much, since the
  CPU and not the network is the bottleneck.

  .. note::

      Due to restrictions in Python's threading module, setting ``processes``
      to anything else than ``1`` will mean that you can't properly abort the
      program with ``^C`` anymore.

.. _pair_config:

Pair Section
------------

::

    [pair pair_name]
    a = ...
    b = ...
    #conflict_resolution = ...

- ``a`` and ``b`` reference the storages to sync by their names.

- ``collections``: Optional, a comma-separated list of collections to
  synchronize. If this parameter is omitted, it is assumed the storages are
  already directly pointing to one collection each. Specifying a collection
  multiple times won't make vdirsyncer sync that collection more than once.

  Furthermore, there are the special values ``from a`` and ``from b``, which
  tell vdirsyncer to try autodiscovery on a specific storage::

      collections = from b,foo,bar  # all in storage b + "foo" + "bar"
      collections = from b,from a  # all in storage a + all in storage b

- ``conflict_resolution``: Optional, define how conflicts should be handled.  A
  conflict occurs when one item changed on both sides since the last sync.
  Valid values are ``a wins`` and ``b wins``. By default, vdirsyncer will show
  an error and abort the synchronization.

.. _storage_config:

Storage Section
---------------

::

    [storage storage_name]
    type = ...

- ``type`` defines which kind of storage is defined. See :ref:`storages`.

- ``read_only`` defines whether the storage should be regarded as a read-only
  storage. The value ``True`` means synchronization will discard any changes
  made to the other side. The value ``False`` implies normal 2-way
  synchronization.

- Any further parameters are passed on to the storage class.

.. _storages:

Supported Storages
==================

.. module:: vdirsyncer.storage

Read-write storages
-------------------

These storages generally support reading and changing of their items. Their
default value for ``read_only`` is ``False``, but can be set to ``True`` if
wished.

.. autoclass:: CaldavStorage

.. autoclass:: CarddavStorage

.. autoclass:: FilesystemStorage

.. autoclass:: SingleFileStorage

Read-only storages
------------------

These storages don't support writing of their items, consequently ``read_only``
is set to ``True`` by default. Changing ``read_only`` to ``False`` on them
leads to an error.

.. autoclass:: HttpStorage
