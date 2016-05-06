========
Tutorial
========

Before starting, :doc:`consider if you actually need vdirsyncer <when>`. There
are better alternatives available for particular usecases.

Installation
============

Unless you want to contribute to vdirsyncer, you should use the packages from
your distribution:

- `ArchLinux (AUR) <https://aur.archlinux.org/packages/vdirsyncer>`_
- `pkgsrc <http://pkgsrc.se/time/py-vdirsyncer>`_
- `Fedora <https://apps.fedoraproject.org/packages/vdirsyncer>`_
- `nixpkg <https://github.com/NixOS/nixpkgs/tree/master/pkgs/tools/misc/vdirsyncer>`_
- `GNU Guix <https://www.gnu.org/software/guix/package-list.html#vdirsyncer>`_
- `homebrew <http://braumeister.org/formula/vdirsyncer>`_
- `Gentoo <https://packages.gentoo.org/packages/dev-python/vdirsyncer>`_
- Debian and Ubuntu don't have packages, but make a manual installation
  especially hard. See :ref:`debian-urllib3`.

If there is no package for your distribution, you'll need to :ref:`install
vdirsyncer manually <manual-installation>`. There is an easy command to
copy-and-paste for this as well, but you should be aware of its consequences.

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

The following example synchronizes ownCloud's
default addressbook to ``~/.contacts/``::

    [pair my_contacts]
    a = my_contacts_local
    b = my_contacts_remote
    collections = null

    [storage my_contacts_local]
    type = filesystem
    path = ~/.contacts/
    fileext = .vcf

    [storage my_contacts_remote]
    type = carddav
    url = https://owncloud.example.com/remote.php/carddav/addressbooks/bob/default/
    username = bob
    password = asdf

.. note::

    Configuration for other servers can be found at :ref:`supported-servers`.

After running ``vdirsyncer discover`` and ``vdirsyncer sync``, ``~/.contacts/``
will contain a bunch of ``.vcf`` files which all contain a contact in ``VCARD``
format each. You can modify their content, add new ones and delete some [1]_,
and your changes will be synchronized to the CalDAV server after you run
``vdirsyncer sync`` again. For further reference, it uses the storages
:storage:`filesystem` and :storage:`carddav`.

.. [1] You'll want to :doc:`use a helper program for this <supported>`.

More Configuration
==================

.. _conflict_resolution:

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

Collection discovery
--------------------

The above configuration only syncs a single addressbook.  This is denoted by
``collections = null`` (collection = addressbook/calendar). We can change this
line to let vdirsyncer automatically sync all addressbooks it can find::

    [pair my_contacts]
    a = my_contacts_local
    b = my_contacts_remote
    collections = ["from a", "from b"]  # changed from `null`

    [storage my_contacts_local]
    type = filesystem
    path = ~/.contacts/
    fileext = .vcf

    [storage my_contacts_remote]
    type = carddav

    # We can simplify this URL here as well. In theory it shouldn't matter.
    url = https://owncloud.example.com/remote.php/carddav/
    username = bob
    password = asdf

With the above configuration, ``vdirsyncer discover`` will fetch all available
collections from the server, and create subdirectories for each of them in
``~/.contacts/`` after confirmation. For example, ownCloud's default
addressbook ``"default"`` would be synchronized to the location
``~/.contacts/default/``.

After that, ``vdirsyncer sync`` will synchronize all your addressbooks as
expected. However, if new collections are created on the server, it will not
automatically start synchronizing those [2]_. You need to run ``vdirsyncer
discover`` again to re-fetch this list instead.

.. [2] Because collections are added rarely, and checking for this case before
   every synchronization isn't worth the overhead.

Metadata synchronization
------------------------

Besides items, vdirsyncer can also synchronize metadata like the addressbook's
or calendar's "human-friendly" name (internally called "displayname") or the
color associated with a calendar. For the purpose of explaining this feature,
let's switch to a different base example. This time we'll synchronize calendars::

    [pair my_calendars]
    a = my_calendars_local
    b = my_calendars_remote
    collections = ["from a", "from b"]
    metadata = ["color"]

    [storage my_calendars_local]
    type = filesystem
    path = ~/.calendars/
    fileext = .ics

    [storage my_calendars_remote]
    type = caldav

    url = https://owncloud.example.com/remote.php/caldav/
    username = bob
    password = asdf

Run ``vdirsyncer discover`` for discovery. Then you can use ``vdirsyncer
metasync`` to synchronize the ``color`` property between your local calendars
in ``~/.calendars/`` and your ownCloud. Locally the color is just represented
as a file called ``color`` within the calendar folder.
