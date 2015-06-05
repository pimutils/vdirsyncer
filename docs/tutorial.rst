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
- Debian and Ubuntu don't have packages, but make a manual installation
  especially hard. See :ref:`debian-urllib3`.

If there is no package for your distribution, you'll need to :ref:`install
vdirsyncer manually <manual-installation>`. There is an easy command to
copy-and-paste for this as well, but you should be aware of its consequences.

Configuration
=============

.. note::

    - The `example.cfg from the repository
      <https://github.com/untitaker/vdirsyncer/blob/master/example.cfg>`_
      contains a very terse version of this.

    - In this example we set up contacts synchronization, but calendar sync
      works almost the same. Just swap ``type = carddav`` for ``type = caldav``
      and ``fileext = .vcf`` for ``fileext = .ics``.

    - Take a look at the :doc:`problems` page if anything doesn't work like
      planned.

By default, *vdirsyncer* looks for its configuration file in the following
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
section <pair_config>`.

This format is copied from OfflineIMAP, where storages are called
repositories and pairs are called accounts.

The following example synchronizes a single CardDAV-addressbook to
``~/.contacts/``::

    [pair my_contacts]
    a = my_contacts_local
    b = my_contacts_remote

    [storage my_contacts_local]
    type = filesystem
    path = ~/.contacts/
    fileext = .vcf

    [storage my_contacts_remote]
    type = carddav
    url = https://owncloud.example.com/remote.php/carddav/addressbooks/bob/default/
    username = bob
    password = asdf

After running ``vdirsyncer sync``, ``~/.contacts/`` will contain a bunch of
``.vcf`` files which all contain a contact in ``VCARD`` format each. You can
modify their content, add new ones and delete some [1]_, and your changes will be
synchronized to the CalDAV server after you run ``vdirsyncer sync`` again. For
further reference, it uses the storages
:py:class:`vdirsyncer.storage.FilesystemStorage` and
:py:class:`vdirsyncer.storage.CarddavStorage`.

.. [1] You'll want to :doc:`use a helper program for this <supported>`.

More Configuration
==================

.. _conflict_resolution:

Conflict resolution
-------------------

It almost seems like it could work. But what if the same item is changed on
both sides? What should vdirsyncer do? By default, it will show an ugly error
message, which is surely a way to avoid the problem. Another way to solve that
ambiguity is to add another line to the *pair* section::

    [pair my_contacts]
    ...
    conflict_resolution = b wins

Earlier we wrote that ``b = my_contacts_remote``, so when vdirsyncer encounters
the situation where an item changed on both sides, it will simply overwrite the
local item with the one from the server. Of course ``a wins`` is also a valid
value.

Collection discovery
--------------------

Configuring each collection (=addressbook/calendar) becomes extremely
repetitive if they are all on the same server. Vdirsyncer can do this for you
by automatically downloading a list of the configured user's collections::

    [pair my_contacts]
    a = my_contacts_local
    b = my_contacts_remote
    collections = from b

    [storage my_contacts_local]
    type = filesystem
    path = ~/.contacts/
    fileext = .vcf

    [storage my_contacts_remote]
    type = carddav
    url = https://owncloud.example.com/remote.php/carddav/
    username = bob
    password = asdf

With the above configuration, vdirsyncer will fetch all available collections
from the server, and create subdirectories for each of them in
``~/.contacts/``. For example, ownCloud's default addressbook ``"default"``
would be synchronized to the location ``~/.contacts/default/``.

Vdirsyncer fetches this list on first sync, and will re-fetch it if you change
your configuration file. However, if new collections are created on the server,
it will not automatically start synchronizing those [2]_. You should run
``vdirsyncer discover`` to re-fetch this list instead.

.. [2] Because collections are added rarely, and checking for this case before
   every synchronization isn't worth the overhead.
