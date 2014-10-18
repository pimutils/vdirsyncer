=============
Configuration
=============


.. _general_config:

General Section
===============

::

    [general]
    status_path = ...
    #processes = 0
    #passwordeval =


- ``status_path``: A directory where vdirsyncer will store metadata for the
  next sync. The data is needed to determine whether a new item means it has
  been added on one side or deleted on the other.

- ``passwordeval`` specifies a command to query for server passwords. The
  command will be called with the username as the first argument, and the
  hostname as the second.

.. versionadded:: 0.3.0
   The ``passwordeval`` parameter.

.. _pair_config:

Pair Section
============

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
  conflict occurs when one item (event, task) changed on both sides since the
  last sync.

  Valid values are:

  - ``a wins`` and ``b wins``, where the whole item is taken from one side.
    Vdirsyncer will not attempt to merge the two items.
  - ``None``, the default, where an error is shown and no changes are done.

.. _storage_config:

Storage Section
===============

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
------------------

.. module:: vdirsyncer.storage

Read-write storages
~~~~~~~~~~~~~~~~~~~

These storages generally support reading and changing of their items. Their
default value for ``read_only`` is ``False``, but can be set to ``True`` if
wished.

.. autoclass:: CaldavStorage

.. autoclass:: CarddavStorage

.. autoclass:: FilesystemStorage

.. autoclass:: SingleFileStorage

Read-only storages
~~~~~~~~~~~~~~~~~~

These storages don't support writing of their items, consequently ``read_only``
is set to ``True`` by default. Changing ``read_only`` to ``False`` on them
leads to an error.

.. autoclass:: HttpStorage
