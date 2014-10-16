==========
vdirsyncer
==========

vdirsyncer synchronizes your calendars and addressbooks between two storages.
The supported storages are CalDAV, CardDAV, arbitrary HTTP resources and `some
more <https://vdirsyncer.readthedocs.org/en/latest/config.html#storages>`_.

It aims to be for CalDAV and CardDAV what `OfflineIMAP
<http://offlineimap.org/>`_ is for IMAP.

.. image:: https://travis-ci.org/untitaker/vdirsyncer.png?branch=master
    :target: https://travis-ci.org/untitaker/vdirsyncer

.. image:: https://coveralls.io/repos/untitaker/vdirsyncer/badge.png?branch=master
    :target: https://coveralls.io/r/untitaker/vdirsyncer?branch=master

Installation and usage
======================

If you already have it installed and want to quickly configure it, copy the
``example.cfg`` to ``~/.vdirsyncer/config`` and edit it.

If that method doesn't work for you or you want a deeper understanding of what
you just did, check out `the tutorial
<https://vdirsyncer.readthedocs.org/en/latest/tutorial.html>`_.

How to run the tests
====================

::

    sh build.sh install_tests
    sh build.sh tests
