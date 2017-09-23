==========
vdirsyncer
==========

- `Documentation <https://vdirsyncer.pimutils.org/en/stable/>`_
- `Source code <https://github.com/pimutils/vdirsyncer>`_

Vdirsyncer is a command-line tool for synchronizing calendars and addressbooks
between a variety of servers and the local filesystem. The most popular usecase
is to synchronize a server with a local folder and use a set of other
:doc:`programs <tutorials/index>` to change the local events and contacts.
Vdirsyncer can then synchronize those changes back to the server.

However, vdirsyncer is not limited to synchronizing between clients and
servers. It can also be used to synchronize calendars and/or addressbooks
between two servers directly.

It aims to be for calendars and contacts what `OfflineIMAP
<http://offlineimap.org/>`_ is for emails.

.. toctree::
   :caption: Users
   :maxdepth: 1

   when
   installation
   tutorial
   ssl-tutorial
   keyring
   partial-sync
   config
   tutorials/index
   problems

.. toctree::
   :caption: Developers
   :maxdepth: 1

   contributing
   vdir

.. toctree::
   :caption: General
   :maxdepth: 1

   packaging
   contact
   changelog
   license
   donations
