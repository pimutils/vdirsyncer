==========
vdirsyncer
==========

vdirsyncer synchronizes your calendars and addressbooks between two storages.
The supported storages are CalDAV, CardDAV and
`vdir <https://github.com/untitaker/vdir>`_.

While i use it daily and haven't experienced data loss (even when vdirsyncer
crashed), i don't know if the documentation is sufficient. If you have any
questions regarding the usage, feel free to open a new issue.

.. image:: https://travis-ci.org/untitaker/vdirsyncer.png?branch=master
    :target: https://travis-ci.org/untitaker/vdirsyncer

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

    sh install_deps.sh
    py.test
