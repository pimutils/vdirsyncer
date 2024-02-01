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
      <https://github.com/pimutils/vdirsyncer/blob/main/config.example>`_
      contains a very terse version of this.

    - In this example we set up contacts synchronization, but calendar sync
      works almost the same. Just swap ``type = "carddav"``
      for ``type = "caldav"`` and ``fileext = ".vcf"``
      for ``fileext = ".ics"``.

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
    status_path = "~/.vdirsyncer/status/"

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

.. [1] You'll want to :doc:`use a helper program for this <tutorials/index>`.

.. [2] Because collections are added rarely, and checking for this case before
   every synchronization isn't worth the overhead.

More Configuration
==================

.. _conflict_resolution_tutorial:

Conflict resolution
-------------------

What if the same item is changed on both sides? What should vdirsyncer
do? Three options are currently provided:

1. vdirsyncer displays an error message (the default);
2. vdirsyncer chooses one alternative version over the other;
3. vdirsyncer starts a command of your choice that is supposed to merge the two alternative versions.

Options 2 and 3 require adding a ``"conflict_resolution"``
parameter to the pair section. Option 2 requires giving either ``"a
wins"`` or ``"b wins"`` as value to the parameter::

    [pair my_contacts]
    ...
    conflict_resolution = "b wins"

Earlier we wrote that ``b = "my_contacts_remote"``, so when vdirsyncer encounters
the situation where an item changed on both sides, it will simply overwrite the
local item with the one from the server.

Option 3 requires specifying as value of ``"conflict_resolution"`` an
array starting with ``"command"`` and containing paths and arguments
to a command. For example::

    [pair my_contacts]
    ...
    conflict_resolution = ["command", "vimdiff"]

In this example, ``vimdiff <a> <b>`` will be called with ``<a>`` and
``<b>`` being two temporary files containing the conflicting
files. The files need to be exactly the same when the command
returns. More arguments can be passed to the command by adding more
elements to the array.

See :ref:`pair_config` for the reference documentation.

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

"Collection" is a collective term for addressbooks and calendars. A Cardav or 
Caldav server can contains several "collections" which correspond to several 
addressbooks or calendar.

Each collection from a storage has a "collection name", a unique identifier for each
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

Advanced collection configuration (server-to-server sync)
---------------------------------------------------------

The examples above are good enough if you want to synchronize a remote server
to a previously empty disk. However, even more trickery is required when you
have two servers with *already existing* collections which you want to
synchronize.

The core problem in this situation is that vdirsyncer pairs collections by
collection name by default (see definition in previous section, basically a
foldername or a remote UUID). When you have two servers, those collection names
may not line up as nicely. Suppose you created two calendars "Test", one on a
NextCloud server and one on iCloud, using their respective web interfaces. The
URLs look something like this::

    NextCloud: https://example.com/remote.php/dav/calendars/user/test/
    iCloud:    https://p-XX.caldav.icloud.com/YYY/calendars/3b4c9995-5c67-4021-9fa0-be4633623e1c

Those are two DAV calendar collections. Their collection names will be ``test``
and ``3b4c9995-5c67-4021-9fa0-be4633623e1c`` respectively, so you don't have a
single name you can address them both with. You will need to manually "pair"
(no pun intended) those collections up like this::

    [pair doublecloud]
    a = "my_nextcloud"
    b = "my_icloud"
    collections = [["mytest", "test", "3b4c9995-5c67-4021-9fa0-be4633623e1c"]]

``mytest`` gives that combination of calendars a nice name you can use when
talking about it, so you would use ``vdirsyncer sync doublecloud/mytest`` to
say: "Only synchronize these two storages, nothing else that may be
configured".

.. note:: Why not use displaynames?

   You may wonder why vdirsyncer just couldn't figure this out by itself. After
   all, you did name both collections "Test" (which is called "the
   displayname"), so why not pair collections by that value?

   There are a few problems with this idea:

   - Two calendars may have the same exact displayname.
   - A calendar may not have a (non-empty) displayname.
   - The displayname might change. Either you rename the calendar, or the
     calendar renames itself because you change a language setting.

   In the end, that property was never designed to be parsed by machines.
