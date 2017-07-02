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

- ``collections``: A list of collections to synchronize when ``vdirsyncer
  sync`` is executed. See also :ref:`collections_tutorial`.

  The special values ``"from a"`` and ``"from b"``, tell vdirsyncer to try
  autodiscovery on a specific storage.

  If the collection you want to sync doesn't have the same name on each side,
  you may also use a value of the form ``["config_name", "name_a", "name_b"]``.
  This will synchronize the collection ``name_a`` on side A with the collection
  ``name_b`` on side B. The ``config_name`` will be used for representation in
  CLI arguments and logging.

  Examples:

  - ``collections = ["from b", "foo", "bar"]`` makes vdirsyncer synchronize the
    collections from side B, and also the collections named "foo" and "bar".

  - ``collections = ["from b", "from a"]`` makes vdirsyncer synchronize all
    existing collections on either side.

  - ``collections = [["bar", "bar_a", "bar_b"], "foo"]`` makes vdirsyncer
    synchronize ``bar_a`` from side A with ``bar_b`` from side B, and also
    synchronize ``foo`` on both sides with each other.

- ``conflict_resolution``: Optional, define how conflicts should be handled.  A
  conflict occurs when one item (event, task) changed on both sides since the
  last sync. See also :ref:`conflict_resolution_tutorial`.

  Valid values are:

  - ``null``, where an error is shown and no changes are done.
  - ``"a wins"`` and ``"b wins"``, where the whole item is taken from one side.
  - ``["command", "vimdiff"]``: ``vimdiff <a> <b>`` will be called where
    ``<a>`` and ``<b>`` are temporary files that contain the item of each side
    respectively. The files need to be exactly the same when the command
    returns.

    - ``vimdiff`` can be replaced with any other command. For example, in POSIX
      ``["command", "cp"]`` is equivalent to ``"a wins"``.
    - Additional list items will be forwarded as arguments. For example,
      ``["command", "vimdiff", "--noplugin"]`` runs ``vimdiff --noplugin``.

  Vdirsyncer never attempts to "automatically merge" the two items.

.. _partial_sync_def:

- ``partial_sync``: Assume A is read-only, B not. If you change items on B,
  vdirsyncer can't sync the changes to A. What should happen instead?

  - ``error``: An error is shown.
  - ``ignore``: The change is ignored. However: Events deleted in B still
    reappear if they're updated in A.
  - ``revert`` (default): The change is reverted on next sync.

  See also :ref:`partial_sync_tutorial`.

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

CalDAV and CardDAV
++++++++++++++++++

.. autostorage:: vdirsyncer.storage.dav.CalDAVStorage

.. autostorage:: vdirsyncer.storage.dav.CardDAVStorage

Google
++++++

Vdirsyncer supports synchronization with Google calendars with the restriction
that ``VTODO`` files are rejected by the server.

Synchronization with Google contacts is less reliable due to negligence of
Google's CardDAV API. **Google's CardDAV implementation is allegedly a disaster
in terms of data safety**. See `this blog post
<https://evertpot.com/google-carddav-issues/>`_ for the details.  Always back
up your data.

At first run you will be asked to authorize application for google account
access.

To use this storage type, you need to install some additional dependencies::

    pip install vdirsyncer[google]

Furthermore you need to register vdirsyncer as an application yourself to
obtain ``client_id`` and ``client_secret``, as `it is against Google's Terms of
Service to hardcode those into opensource software
<https://developers.google.com/terms/?hl=th#b-confidential-matters>`_:

1. Go to the `Google API Manager <https://console.developers.google.com>`_ and
   create a new project under any name.

2. Within that project, enable the "CalDAV" and "CardDAV" APIs (**not** the
   Calendar and Contacts APIs, those are different and won't work). There should
   be a searchbox where you can just enter those terms.

3. In the sidebar, select "Credentials" and create a new "OAuth Client ID". The
   application type is "Other".
   
   You'll be prompted to create a OAuth consent screen first. Fill out that
   form however you like.

4. Finally you should have a Client ID and a Client secret. Provide these in
   your storage config.

The ``token_file`` parameter should be a filepath where vdirsyncer can later
store authentication-related data. You do not need to create the file itself
or write anything to it.

.. note::

    You need to configure which calendars Google should offer vdirsyncer using
    a rather hidden `settings page
    <https://calendar.google.com/calendar/syncselect>`_.

.. autostorage:: vdirsyncer.storage.google.GoogleCalendarStorage

.. autostorage:: vdirsyncer.storage.google.GoogleContactsStorage

EteSync
+++++++

`EteSync <https://www.etesync.com/>`_ is a new cloud provider for end to end
encrypted contacts and calendar storage. Vdirsyncer contains **experimental**
support for it.

To use it, you need to install some optional dependencies::

    pip install vdirsyncer[etesync]

On first usage you will be prompted for the service password and the encryption
password. Neither are stored.

.. autostorage:: vdirsyncer.storage.etesync.EtesyncContacts

.. autostorage:: vdirsyncer.storage.etesync.EtesyncCalendars

Local
+++++

.. autostorage:: vdirsyncer.storage.filesystem.FilesystemStorage

.. autostorage:: vdirsyncer.storage.singlefile.SingleFileStorage


Read-only storages
++++++++++++++++++

These storages don't support writing of their items, consequently ``read_only``
is set to ``true`` by default. Changing ``read_only`` to ``false`` on them
leads to an error.

.. autostorage:: vdirsyncer.storage.http.HttpStorage
