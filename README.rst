==========
vdirsyncer
==========

vdirsyncer synchronizes your calendars and addressbooks between two storages.
The supported storages are CalDAV, CardDAV, arbitrary HTTP resources and `some
more <https://vdirsyncer.readthedocs.org/en/latest/api.html#storages>`_.

It aims to be for CalDAV and CardDAV what `OfflineIMAP
<http://offlineimap.org/>`_ is for IMAP.

.. image:: https://travis-ci.org/untitaker/vdirsyncer.png?branch=master
    :target: https://travis-ci.org/untitaker/vdirsyncer

.. image:: https://coveralls.io/repos/untitaker/vdirsyncer/badge.png?branch=master
    :target: https://coveralls.io/r/untitaker/vdirsyncer?branch=master

How to use
==========

vdirsyncer requires Python >= 2.7 or Python >= 3.3.

As all Python packages, vdirsyncer can be installed with ``pip``::

    pip install --user vdirsyncer

Then copy ``example.cfg`` to ``~/.vdirsyncer/config`` and edit it.

Run ``vdirsyncer --help`` and check out `the documentation
<https://vdirsyncer.readthedocs.org/>`_.

How to run the tests
====================

::

    sh build.sh install
    sh build.sh run
