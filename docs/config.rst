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

.. note::

    Please also see :ref:`supported-servers`, as some servers may not work
    well.

.. storage:: caldav

    CalDAV.

    ::

        [storage example_for_caldav]
        type = "caldav"
        #start_date = null
        #end_date = null
        #item_types = []
        url = "..."
        #username = ""
        #password = ""
        #verify = true
        #auth = null
        #useragent = "vdirsyncer/0.16.4"
        #verify_fingerprint = null
        #auth_cert = null

    You can set a timerange to synchronize with the parameters ``start_date``
    and ``end_date``. Inside those parameters, you can use any Python
    expression to return a valid :py:class:`datetime.datetime` object. For
    example, the following would synchronize the timerange from one year in the
    past to one year in the future::

        start_date = "datetime.now() - timedelta(days=365)"
        end_date = "datetime.now() + timedelta(days=365)"

    Either both or none have to be specified. The default is to synchronize
    everything.

    You can set ``item_types`` to restrict the *kind of items* you want to
    synchronize. For example, if you want to only synchronize events (but don't
    download any tasks from the server), set ``item_types = ["VEVENT"]``. If
    you want to synchronize events and tasks, but have some ``VJOURNAL`` items
    on the server you don't want to synchronize, use ``item_types = ["VEVENT",
    "VTODO"]``.

    :param start_date: Start date of timerange to show, default -inf.
    :param end_date: End date of timerange to show, default +inf.
    :param item_types: Kind of items to show. The default, the empty list, is
        to show all. This depends on particular features on the server, the
        results are not validated.
    :param url: Base URL or an URL to a calendar.
    :param username: Username for authentication.
    :param password: Password for authentication.
    :param verify: Verify SSL certificate, default True. This can also be a
        local path to a self-signed SSL certificate. See :ref:`ssl-tutorial`
        for more information.
    :param verify_fingerprint: Optional. SHA1 or MD5 fingerprint of the
        expected server certificate. See :ref:`ssl-tutorial` for more
        information.
    :param auth: Optional. Either ``basic``, ``digest`` or ``guess``. The
        default is preemptive Basic auth, sending credentials even if server
        didn't request them. This saves from an additional roundtrip per
        request. Consider setting ``guess`` if this causes issues with your
        server.
    :param auth_cert: Optional. Either a path to a certificate with a client
        certificate and the key or a list of paths to the files with them.
    :param useragent: Default ``vdirsyncer``.


.. storage:: carddav

   CardDAV.

   ::

     [storage example_for_carddav]
     type = "carddav"
     url = "..."
     #username = ""
     #password = ""
     #verify = true
     #auth = null
     #useragent = "vdirsyncer/0.16.4"
     #verify_fingerprint = null
     #auth_cert = null

   :param url: Base URL or an URL to an addressbook.
   :param username: Username for authentication.
   :param password: Password for authentication.
   :param verify: Verify SSL certificate, default True. This can also be a
                  local path to a self-signed SSL certificate. See
                  :ref:`ssl-tutorial` for more information.
   :param verify_fingerprint: Optional. SHA1 or MD5 fingerprint of the expected
                              server certificate. See :ref:`ssl-tutorial` for
                              more information.
   :param auth: Optional. Either ``basic``, ``digest`` or ``guess``. The
                default is preemptive Basic auth, sending credentials even if
                server didn't request them. This saves from an additional
                roundtrip per request. Consider setting ``guess`` if this
                causes issues with your server.
   :param auth_cert: Optional. Either a path to a certificate with a client
                     certificate and the key or a list of paths to the files
                     with them.
   :param useragent: Default ``vdirsyncer``.

Google
++++++

Vdirsyncer supports synchronization with Google calendars with the restriction
that ``VTODO`` files are rejected by the server.

Synchronization with Google contacts is less reliable due to negligence of
Google's CardDAV API. **Google's CardDAV implementation is allegedly a disaster
in terms of data safety**. See `this blog post
<https://evertpot.com/google-carddav-issues/>`_ for the details.  Always back
up your data.

At first run you will be asked to authorize application for Google account
access.

To use this storage type, you need to install some additional dependencies::

    pip install vdirsyncer[google]

Furthermore you need to register vdirsyncer as an application yourself to
obtain ``client_id`` and ``client_secret``, as it is against Google's Terms of
Service to hardcode those into opensource software [googleterms]_:

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

.. [googleterms] See `ToS <https://developers.google.com/terms/?hl=th>`_,
   section "Confidential Matters".

.. note::

    You need to configure which calendars Google should offer vdirsyncer using
    a rather hidden `settings page
    <https://calendar.google.com/calendar/syncselect>`_.

.. storage:: google_calendar

   Google calendar.

   ::

       [storage example_for_google_calendar]
       type = "google_calendar"
       token_file = "..."
       client_id = "..."
       client_secret = "..."
       #start_date = null
       #end_date = null
       #item_types = []

   Please refer to :storage:`caldav` regarding the ``item_types`` and timerange parameters.

   :param token_file: A filepath where access tokens are stored.
   :param client_id/client_secret: OAuth credentials, obtained from the Google
                                   API Manager.

.. storage:: google_contacts

   Google contacts.

   ::

       [storage example_for_google_contacts]
       type = "google_contacts"
       token_file = "..."
       client_id = "..."
       client_secret = "..."

   :param token_file: A filepath where access tokens are stored.
   :param client_id/client_secret: OAuth credentials, obtained from the Google
                                   API Manager.

EteSync
+++++++

`EteSync <https://www.etesync.com/>`_ is a new cloud provider for end to end
encrypted contacts and calendar storage. Vdirsyncer contains **experimental**
support for it.

To use it, you need to install some optional dependencies::

    pip install vdirsyncer[etesync]

On first usage you will be prompted for the service password and the encryption
password. Neither are stored.

.. storage:: etesync_contacts

    Contacts for etesync.

    ::

        [storage example_for_etesync_contacts]
        email = ...
        secrets_dir = ...
        #server_path = ...
        #db_path = ...

   :param email: The email address of your account.
   :param secrets_dir: A directory where vdirsyncer can store the encryption
                       key and authentication token.
   :param server_url: Optional. URL to the root of your custom server.
   :param db_path: Optional. Use a different path for the database.

.. storage:: etesync_calendars

    Calendars for etesync.

    ::

        [storage example_for_etesync_calendars]
        email = ...
        secrets_dir = ...
        #server_path = ...
        #db_path = ...

    :param email: The email address of your account.
    :param secrets_dir: A directory where vdirsyncer can store the encryption
                        key and authentication token.
    :param server_url: Optional. URL to the root of your custom server.
    :param db_path: Optional. Use a different path for the database.

Local
+++++

.. storage:: filesystem

    Saves each item in its own file, given a directory.

    ::

      [storage example_for_filesystem]
      type = "filesystem"
      path = "..."
      fileext = "..."
      #encoding = "utf-8"
      #post_hook = null

    Can be used with `khal <http://lostpackets.de/khal/>`_. See :doc:`vdir` for
    a more formal description of the format.

    Directories with a leading dot are ignored to make usage of e.g. version
    control easier.

    :param path: Absolute path to a vdir/collection. If this is used in
        combination with the ``collections`` parameter in a pair-section, this
        should point to a directory of vdirs instead.
    :param fileext: The file extension to use (e.g. ``.txt``). Contained in the
        href, so if you change the file extension after a sync, this will
        trigger a re-download of everything (but *should* not cause data-loss
        of any kind).
    :param encoding: File encoding for items, both content and filename.
    :param post_hook: A command to call for each item creation and
        modification. The command will be called with the path of the
        new/updated file.

.. storage:: singlefile

    Save data in single local ``.vcf`` or ``.ics`` file.

    The storage basically guesses how items should be joined in the file.

    .. versionadded:: 0.1.6

    .. note::
        This storage is very slow, and that is unlikely to change. You should
        consider using :storage:`filesystem` if it fits your usecase.

    :param path: The filepath to the file to be written to. If collections are
        used, this should contain ``%s`` as a placeholder for the collection
        name.
    :param encoding: Which encoding the file should use. Defaults to UTF-8.

    Example for syncing with :storage:`caldav`::

        [pair my_calendar]
        a = my_calendar_local
        b = my_calendar_remote
        collections = ["from a", "from b"]

        [storage my_calendar_local]
        type = "singlefile"
        path = ~/.calendars/%s.ics

        [storage my_calendar_remote]
        type = "caldav"
        url = https://caldav.example.org/
        #username =
        #password =

    Example for syncing with :storage:`caldav` using a ``null`` collection::

        [pair my_calendar]
        a = my_calendar_local
        b = my_calendar_remote

        [storage my_calendar_local]
        type = "singlefile"
        path = ~/my_calendar.ics

        [storage my_calendar_remote]
        type = "caldav"
        url = https://caldav.example.org/username/my_calendar/
        #username =
        #password =

Read-only storages
++++++++++++++++++

These storages don't support writing of their items, consequently ``read_only``
is set to ``true`` by default. Changing ``read_only`` to ``false`` on them
leads to an error.

.. storage:: http

    Use a simple ``.ics`` file (or similar) from the web.
    ``webcal://``-calendars are supposed to be used with this, but you have to
    replace ``webcal://`` with ``http://``, or better, ``https://``.

    ::

        [pair holidays]
        a = holidays_local
        b = holidays_remote
        collections = null

        [storage holidays_local]
        type = "filesystem"
        path = ~/.config/vdir/calendars/holidays/
        fileext = .ics

        [storage holidays_remote]
        type = "http"
        url = https://example.com/holidays_from_hicksville.ics

    Too many WebCAL providers generate UIDs of all ``VEVENT``-components
    on-the-fly, i.e. all UIDs change every time the calendar is downloaded.
    This leads many synchronization programs to believe that all events have
    been deleted and new ones created, and accordingly causes a lot of
    unnecessary uploads and deletions on the other side. Vdirsyncer completely
    ignores UIDs coming from :storage:`http` and will replace them with a hash
    of the normalized item content.

    :param url: URL to the ``.ics`` file.
    :param username: Username for authentication.
    :param password: Password for authentication.
    :param verify: Verify SSL certificate, default True. This can also be a
        local path to a self-signed SSL certificate. See :ref:`ssl-tutorial`
        for more information.
    :param verify_fingerprint: Optional. SHA1 or MD5 fingerprint of the
        expected server certificate. See :ref:`ssl-tutorial` for more
        information.
    :param auth: Optional. Either ``basic``, ``digest`` or ``guess``. The
        default is preemptive Basic auth, sending credentials even if server
        didn't request them. This saves from an additional roundtrip per
        request. Consider setting ``guess`` if this causes issues with your
        server.
    :param auth_cert: Optional. Either a path to a certificate with a client
        certificate and the key or a list of paths to the files with them.
    :param useragent: Default ``vdirsyncer``.
