==========
vdirsyncer
==========

.. image:: https://travis-ci.org/untitaker/vdirsyncer.png?branch=master
    :target: https://travis-ci.org/untitaker/vdirsyncer

vdirsyncer synchronizes your calendars and addressbooks between two storages.
The supported storages are CalDAV, CardDAV and
`vdir <https://github.com/untitaker/vdir>`_.

While i use it daily and haven't experienced data loss (even when vdirsyncer
crashed), i don't know if the documentation is sufficient. If you have any
questions regarding the usage, feel free to open a new issue.

It aims to be for CalDAV and CardDAV what
`OfflineIMAP <http://offlineimap.org/>`_ is for IMAP.

How to use
==========

Copy ``example.cfg`` to ``~/.vdirsyncer/config`` and edit it. You can use the
`VDIRSYNCER_CONFIG` environment variable to change the path vdirsyncer will
read the config from.

Run ``vdirsyncer --help``.

How to run the tests
====================

::

    sh install-deps.sh
    sh run-tests.sh

The environment variable ``DAV_SERVER`` specifies which CalDAV/CardDAV server
to test against. It has to be set for both scripts, ``install-deps.sh`` and
``run-tests.sh``.

  - ``DAV_SERVER=radicale``: The default, installs the latest Radicale release
    from PyPI. Very fast, because no additional processes are needed.
  - ``DAV_SERVER=radicale_git``: Same as ``radicale``, except that the
    installation happens from their git repo. ``install-deps.sh`` is slightly
    slower with this.
  - ``DAV_SERVER=owncloud``: Uses latest ownCloud release. Very slow
    installation, very slow tests.
