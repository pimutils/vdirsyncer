==========
vdirsyncer
==========

.. image:: https://travis-ci.org/untitaker/vdirsyncer.png?branch=master
    :target: https://travis-ci.org/untitaker/vdirsyncer

vdirsyncer synchronizes your calendars and addressbooks between two storages.
The supported storages are CalDAV, CardDAV, arbitrary HTTP resources and
`vdir <https://github.com/untitaker/vdir>`_.

While i use it daily and haven't experienced data loss (even when vdirsyncer
crashed), i don't know if the documentation is sufficient. If you have any
questions regarding the usage, feel free to open a new issue.

It aims to be for CalDAV and CardDAV what
`OfflineIMAP <http://offlineimap.org/>`_ is for IMAP.

CardDAV/CalDAV Server Support
=====================

vdirsyncer is currently tested against the latest versions Radicale and
ownCloud. While Radicale seems to work perfectly, ownCloud currently has
problems detecting collisions and race-conditions. However, given that this is
a problem with every setup involving ownCloud, and that ownCloud is widely
used, it apparently isn't big enough of a problem yet.

See `Bug #16 <https://github.com/untitaker/vdirsyncer/issues/16>`_ for
informations on problems with ownCloud.

How to use
==========

Copy ``example.cfg`` to ``~/.vdirsyncer/config`` and edit it. You can use the
`VDIRSYNCER_CONFIG` environment variable to change the path vdirsyncer will
read the config from.

Run ``vdirsyncer --help``. If you experience any problems, consult the `wiki's
troubleshooting page
<https://github.com/untitaker/vdirsyncer/wiki/Troubleshooting>`_ or create a
new issue.

How to run the tests
====================

::

    sh install-deps.sh
    py.test tests/
