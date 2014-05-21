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

 - ``processes``: Optional, defines the amount of maximal connections to use
   for syncing.  By default there is no limit, which means vdirsyncer will try
   to open a connection for each collection to be synced. The value ``0`` is
   ignored. Setting this to ``1`` will only synchronize one collection at a
   time.
   
   While this often greatly increases performance, you might have valid reasons
   to set this to a smaller number. For example, your DAV server running on a
   Raspberry Pi is so slow that multiple connections don't help much, since the
   CPU and not the network is the bottleneck.

.. _pair_config:

Pair Section
------------

::
    [pair pair_name]
    a = ...
    b = ...
    #conflict_resolution = ...

  - ``a`` and ``b`` reference the storages to sync by their names.

  - ``conflict_resolution``: Optional, define how conflicts should be handled.
    A conflict occurs when one item changed on both sides since the last sync.
    Valid values are ``a wins`` and ``b wins``. By default, vdirsyncer will
    show an error and abort the synchronization.

.. _storage_config:

Storage Section
---------------

::
    [storage storage_name]
    type = ...

  - ``type`` defines which kind of storage is defined. See :ref:`storages`.

  - Any further parameters are passed on to the storage class.

.. _storages:

Supported Storages
==================

.. module:: vdirsyncer.storage

.. autoclass:: CaldavStorage

.. autoclass:: CarddavStorage

.. autoclass:: FilesystemStorage

.. autoclass:: HttpStorage

.. autoclass:: SingleFileStorage
