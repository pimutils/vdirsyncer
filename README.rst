==========
vdirsyncer
==========

- `Documentation <https://vdirsyncer.readthedocs.org/en/stable/>`_
- `Source code <https://github.com/untitaker/vdirsyncer>`_

Vdirsyncer synchronizes your calendars and addressbooks between two storages_.
The most popular purpose is to synchronize a CalDAV/CardDAV server with a local
folder or file. The local data can then be accessed via a variety of programs_,
none of which have to know or worry about syncing to a server.

.. _storages: https://vdirsyncer.readthedocs.org/en/latest/config.html#storages
.. _programs: https://vdirsyncer.readthedocs.org/en/stable/supported.html

It aims to be for CalDAV and CardDAV what `OfflineIMAP
<http://offlineimap.org/>`_ is for IMAP.

.. image:: https://travis-ci.org/untitaker/vdirsyncer.png?branch=master
    :target: https://travis-ci.org/untitaker/vdirsyncer

.. image:: https://codecov.io/github/untitaker/vdirsyncer/coverage.svg?branch=master
    :target: https://codecov.io/github/untitaker/vdirsyncer?branch=master

Installation and usage
======================

If you already have it installed and want to quickly configure it, copy the
``config.example`` to ``~/.vdirsyncer/config`` [1]_ and edit it. Then run
``vdirsyncer sync``.

If that method doesn't work for you or you want a deeper understanding of what
you just did, check out `the tutorial
<https://vdirsyncer.readthedocs.org/en/stable/tutorial.html>`_.

.. [1] Or ``$XDG_CONFIG_HOME/vdirsyncer/config`` (normally
   ``~/.config/vdirsyncer/config``) for XDG-Basedir spec compliance.

Donations
=========

- IBAN on request
- Bitcoin: ``16sSHxZm263WHR9P9PJjCxp64jp9ooXKVt``
- Bountysource:

  .. image:: https://img.shields.io/bountysource/team/vdirsyncer/activity.svg
      :target: https://www.bountysource.com/teams/vdirsyncer

- Flattr:

  .. image:: https://api.flattr.com/button/flattr-badge-large.png
      :target: https://flattr.com/submit/auto?user_id=untitaker&url=https%3A%2F%2Fgithub.com%2Funtitaker%2Fvdirsyncer
