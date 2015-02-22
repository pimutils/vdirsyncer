Reporting bugs
==============

* Make sure you have the latest version by executing ``pip install --user
  --upgrade vdirsyncer``.

* Include the Python version, your configuration, the commands you're
  executing, and their output.

* Use ``--verbosity=DEBUG`` when including output from vdirsyncer.

Suggesting features
===================

If you're suggesting a feature, keep in mind that vdirsyncer tries not to be a
full calendar or contacts client, but rather just the piece of software that
synchronizes all the data. `Take a look at the documentation for software
working with vdirsyncer
<http://vdirsyncer.readthedocs.org/en/latest/supported.html>`_.

Submitting patches, pull requests
=================================

* **Discuss everything in the issue tracker first** (or contact me somehow
  else) before implementing it.

* Make sure the tests pass. See below for running them.

* But not because you wrote too few tests.

* Add yourself to ``AUTHORS.rst``, and add a note to ``CHANGELOG.rst`` too.

Running tests, how to set up your development environment
=========================================================

For many patches, it might suffice to just let Travis run the tests. However,
Travis is slow, so you might want to run them locally too. For this, set up a
virtualenv_ and run this inside of it::

    make install-test
    make install-style

This will install all dependencies required for the integration tests against
the latest release of Radicale (a CalDAV server). Then you can run::

    make test
    make style  # Stylechecker

If you have any questions, feel free to open issues about it.

.. _virtualenv: http://virtualenv.readthedocs.org/
