.. _claws-mail-tutorial:

Vdirsyncer with Claws Mail
==========================

First of all, Claws-Mail only supports **read-only** functions for vCards. It
can only read contacts, but there's no editor.

Preparation
-----------

We need to install vdirsyncer, for that look :doc:`here </installation>`.  Then
we need to create some folders::

    mkdir ~/.vdirsyncer
    mkdir ~/.contacts

Configuration
-------------

Now we create the configuration for vdirsyncer. Open
``~/.vdirsyncer/config`` with a text editor. The config should look like
this:

.. code:: ini

    [general]
    status_path = "~/.vdirsyncer/status/"

    [storage local]
    type = "singlefile"
    path = "~/.contacts/%s.vcf"

    [storage online]
    type = "carddav"
    url = "CARDDAV_LINK"
    username = "USERNAME"
    password = "PASSWORD"
    read_only = true

    [pair contacts]
    a = "local"
    b = "online"
    collections = ["from a", "from b"]
    conflict_resolution = "b wins"

- In the general section, we define the status folder path, for discovered
  collections and generally stuff that needs to persist between syncs.
- In the local section we define that all contacts should be sync in a single
  file and the path for the contacts.
- In the online section you must change the url, username and password to your
  setup. We also set the storage to read-only such that no changes get
  synchronized back. Claws-Mail should not be able to do any changes anyway,
  but this is one extra safety step in case files get corrupted or vdirsyncer
  behaves eratically. You can leave that part out if you want to be able to
  edit those files locally.
- In the last section we configure that online contacts win in a conflict
  situation. Configure this part however you like. A correct value depends on
  which side is most likely to be up-to-date.

Sync
----

Now we discover and sync our contacts::

    vdirsyncer discover contacts
    vdirsyncer sync contacts

Claws Mail
----------

Open Claws-Mail. Got to **Tools** => **Addressbook**.

Click on **Addressbook** => **New vCard**. Choose a name for the book.

Then search for the for the vCard in the folder **~/.contacts/**. Click
ok, and you we will see your contacts.

.. note::
    
    Claws-Mail shows only contacts that have a mail address.

Crontab
-------

On the end we create a crontab, so that vdirsyncer syncs automatically
every 30 minutes our contacts::

    contab -e

On the end of that file enter this line::

    */30 * * * * /usr/local/bin/vdirsyncer sync > /dev/null

And you're done!
