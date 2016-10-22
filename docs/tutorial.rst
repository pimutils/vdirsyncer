========
Tutorial
========

Before starting, :doc:`consider if you actually need vdirsyncer <when>`. There
are better alternatives available for particular usecases.

Installation
============

See :ref:`installation`.

Configuration
=============

.. note::

    - The `config.example from the repository
      <https://github.com/pimutils/vdirsyncer/blob/master/config.example>`_
      contains a very terse version of this.

    - In this example we set up contacts synchronization, but calendar sync
      works almost the same. Just swap ``type = carddav`` for ``type = caldav``
      and ``fileext = .vcf`` for ``fileext = .ics``.

    - Take a look at the :doc:`problems` page if anything doesn't work like
      planned.

By default, vdirsyncer looks for its configuration file in the following
locations:

- The file pointed to by the ``VDIRSYNCER_CONFIG`` environment variable.
- ``~/.vdirsyncer/config``.
- ``$XDG_CONFIG_HOME/vdirsyncer/config``, which is normally
  ``~/.config/vdirsyncer/config``. See the XDG-Basedir_ specification.

.. _XDG-Basedir: http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html#variables

The config file should start with a :ref:`general section <general_config>`,
where the only required parameter is ``status_path``. The following is a
minimal example::

    [general]
    status_path = ~/.vdirsyncer/status/

After the general section, an arbitrary amount of *pair and storage sections*
might come.

In vdirsyncer, synchronization is always done between two storages. Such
storages are defined in :ref:`storage sections <storage_config>`, and which
pairs of storages should actually be synchronized is defined in :ref:`pair
section <pair_config>`.  This format is copied from OfflineIMAP, where storages
are called repositories and pairs are called accounts.

The following example synchronizes ownCloud's addressbooks to ``~/.contacts/``::


    [pair my_contacts]
    a = "my_contacts_local"
    b = "my_contacts_remote"
    collections = ["from a", "from b"]

    [storage my_contacts_local]
    type = "filesystem"
    path = "~/.contacts/"
    fileext = ".vcf"

    [storage my_contacts_remote]
    type = "carddav"

    # We can simplify this URL here as well. In theory it shouldn't matter.
    url = "https://owncloud.example.com/remote.php/carddav/"
    username = "bob"
    password = "asdf"

.. note::

    Configuration for other servers can be found at :ref:`supported-servers`.

After running ``vdirsyncer discover`` and ``vdirsyncer sync``, ``~/.contacts/``
will contain subfolders for each addressbook, which in turn will contain a
bunch of ``.vcf`` files which all contain a contact in ``VCARD`` format each.
You can modify their contents, add new ones and delete some [1]_, and your
changes will be synchronized to the CalDAV server after you run ``vdirsyncer
sync`` again. For further reference, it uses the storages :storage:`filesystem`
and :storage:`carddav`.

However, if new collections are created on the server, it will not
automatically start synchronizing those [2]_. You need to run ``vdirsyncer
discover`` again to re-fetch this list instead.

.. [1] You'll want to :doc:`use a helper program for this <supported>`.

.. [2] Because collections are added rarely, and checking for this case before
   every synchronization isn't worth the overhead.

More Configuration
==================

.. _conflict_resolution_tutorial:

Conflict resolution
-------------------

What if the same item is changed on both sides? What should vdirsyncer do? By
default, it will show an ugly error message, which is surely a way to avoid the
problem. Another way to solve that ambiguity is to add another line to the
pair section::

    [pair my_contacts]
    ...
    conflict_resolution = b wins

Earlier we wrote that ``b = my_contacts_remote``, so when vdirsyncer encounters
the situation where an item changed on both sides, it will simply overwrite the
local item with the one from the server. Of course ``a wins`` is also a valid
value.

.. _metasync_tutorial:

Metadata synchronization
------------------------

Besides items, vdirsyncer can also synchronize metadata like the addressbook's
or calendar's "human-friendly" name (internally called "displayname") or the
color associated with a calendar. For the purpose of explaining this feature,
let's switch to a different base example. This time we'll synchronize calendars::

    [pair my_calendars]
    a = "my_calendars_local"
    b = "my_calendars_remote"
    collections = ["from a", "from b"]
    metadata = ["color"]

    [storage my_calendars_local]
    type = "filesystem"
    path = "~/.calendars/"
    fileext = ".ics"

    [storage my_calendars_remote]
    type = "caldav"

    url = "https://owncloud.example.com/remote.php/caldav/"
    username = "bob"
    password = "asdf"

Run ``vdirsyncer discover`` for discovery. Then you can use ``vdirsyncer
metasync`` to synchronize the ``color`` property between your local calendars
in ``~/.calendars/`` and your ownCloud. Locally the color is just represented
as a file called ``color`` within the calendar folder.

.. _collections_tutorial:

More information about collections
----------------------------------

"Collection" is a collective term for addressbooks and calendars. Each
collection from a storage has a "collection name", a unique identifier for each
collection. In the case of :storage:`filesystem`-storage, this is the name of the
directory that represents the collection, in the case of the DAV-storages this
is the last segment of the URL. We use this identifier in the ``collections``
parameter in the ``pair``-section.

This identifier doesn't change even if you rename your calendar in whatever UI
you have, because that only changes the so-called "displayname" property [3]_.
On some servers (iCloud, Google) this identifier is randomly generated and has
no correlation with the displayname you chose.

.. [3] Which you can also synchronize with ``metasync`` using ``metadata =
   ["displayname"]``.

There are three collection names that have a special meaning:

- ``"from a"``, ``"from b"``: A placeholder for all collections that can be
  found on side A/B when running ``vdirsyncer discover``.
- ``null``: The parameters give to the storage are exact and require no discovery.

The last one requires a bit more explanation.  Assume this config which
synchronizes two directories of addressbooks::

    [pair foobar]
    a = "foo"
    b = "bar"
    collections = ["from a", "from b"]

    [storage foo]
    type = "filesystem"
    fileext = ".vcf"
    path = "./contacts_foo/"

    [storage bar]
    type = "filesystem"
    fileext = ".vcf"
    path = "./contacts_bar/"

As we saw previously this will synchronize all collections in
``./contacts_foo/`` with each same-named collection in ``./contacts_bar/``. If
there's a collection that exists on one side but not the other, vdirsyncer will
ask whether to create that folder on the other side.

If we set ``collections = null``, ``./contacts_foo/`` and ``./contacts_bar/``
are no longer treated as folders with collections, but as collections
themselves. This means that ``./contacts_foo/`` and ``./contacts_bar/`` will
contain ``.vcf``-files, not subfolders that contain ``.vcf``-files.

This is useful in situations where listing all collections fails because your
DAV-server doesn't support it, for example. In this case, you can set ``url``
of your :storage:`carddav`- or :storage:`caldav`-storage to a URL that points
to your CalDAV/CardDAV collection directly.

Note that not all storages support the ``null``-collection, for example
:storage:`google_contacts` and :storage:`google_calendar` don't.
