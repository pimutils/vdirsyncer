==========
vdirsyncer
==========

.. image:: https://builds.sr.ht/~whynothugo/vdirsyncer.svg
  :target: https://builds.sr.ht/~whynothugo/vdirsyncer
  :alt: CI status

.. image:: https://codecov.io/github/pimutils/vdirsyncer/coverage.svg?branch=main
  :target: https://codecov.io/github/pimutils/vdirsyncer?branch=main
  :alt: Codecov coverage report

.. image:: https://readthedocs.org/projects/vdirsyncer/badge/
  :target: https://vdirsyncer.rtfd.org/
  :alt: documentation

.. image:: https://img.shields.io/pypi/v/vdirsyncer.svg
  :target: https://pypi.python.org/pypi/vdirsyncer
  :alt: version on pypi

.. image:: https://img.shields.io/badge/deb-packagecloud.io-844fec.svg
  :target: https://packagecloud.io/pimutils/vdirsyncer
  :alt: Debian packages

.. image:: https://img.shields.io/pypi/l/vdirsyncer.svg
  :target: https://github.com/pimutils/vdirsyncer/blob/main/LICENCE
  :alt: licence: BSD

- `Documentation <https://vdirsyncer.pimutils.org/en/stable/>`_
- `Source code <https://github.com/pimutils/vdirsyncer>`_

Vdirsyncer is a command-line tool for synchronizing calendars and addressbooks
between a variety of servers and the local filesystem. The most popular usecase
is to synchronize a server with a local folder and use a set of other programs_
to change the local events and contacts. Vdirsyncer can then synchronize those
changes back to the server.

However, vdirsyncer is not limited to synchronizing between clients and
servers. It can also be used to synchronize calendars and/or addressbooks
between two servers directly.

It aims to be for calendars and contacts what `OfflineIMAP
<http://offlineimap.org/>`_ is for emails.

.. _programs: https://vdirsyncer.pimutils.org/en/latest/tutorials/

Links of interest
=================

* Check out `the tutorial
  <https://vdirsyncer.pimutils.org/en/stable/tutorial.html>`_ for basic
  usage.

* `Contact information
  <https://vdirsyncer.pimutils.org/en/stable/contact.html>`_

* `How to contribute to this project
  <https://vdirsyncer.pimutils.org/en/stable/contributing.html>`_

* `Donations <https://vdirsyncer.pimutils.org/en/stable/donations.html>`_

Dockerized
=================
If you want to run `Vdirsyncer <https://vdirsyncer.pimutils.org/en/stable/>`_ in a
Docker environment, you can check out the following GitHub Repository:

* `Vdirsyncer DOCKERIZED <https://github.com/Bleala/Vdirsyncer-DOCKERIZED>`_

Note: This is an unofficial Docker build, it is maintained by `Bleala <https://github.com/Bleala>`_.

License
=======

Licensed under the 3-clause BSD license, see ``LICENSE``.
