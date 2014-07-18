========
Tutorial
========

Installation
============

- Make sure you have Python 2.7+ or Python 3.3+ installed.

- ``pip install --user vdirsyncer``

- Check if the ``vdirsyncer`` command is available.

Configuration
=============

.. note::
    The `example.cfg from the repository
    <https://github.com/untitaker/vdirsyncer/blob/master/example.cfg>`_
    contains a very terse version of this.

By default, *vdirsyncer* looks for its configuration file at
``~/.vdirsyncer/config``. You can use the ``VDIRSYNCER_CONFIG`` environment
variable to change this path.

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
modify their content, add new ones and delete some, and your changes will be
synchronized to the CalDAV server after you run ``vdirsyncer sync`` again. For
further reference, it uses the storages
:py:class:`vdirsyncer.storage.FilesystemStorage` and
:py:class:`vdirsyncer.storage.CarddavStorage`.

But what if we want to synchronize multiple addressbooks from the same server?
Of course we could create new pairs and storages for each addressbook, but that
is very tedious to do. Instead we will use a shortcut:

- Remove the last segment from the URL, so that it ends with ``.../bob/``
  instead of ``.../bob/default/``.

- Add the following line to the *pair* section::

      [pair my_contacts]
      ...
      collections = default,work

This will synchronize
``https://owncloud.example.com/remote.php/carddav/addressbooks/bob/default/``
with ``~/.contacts/default/`` and
``https://owncloud.example.com/remote.php/carddav/addressbooks/bob/work/`` with
``~/.contacts/work/``. Under the hood, vdirsyncer also just copies the pairs
and storages for each collection and appends the collection name to the path or
URL.

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

Calendar sync works almost the same. Just swap ``type = carddav`` for ``type =
caldav`` and ``fileext = .vcf`` for ``fileext = .ics``.
