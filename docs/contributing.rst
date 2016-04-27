============================
Contributing to this project
============================

**Important:** Please read :doc:`contact` for questions and support requests.

The issue tracker
=================

We use `GitHub issues <https://github.com/pimutils/vdirsyncer/issues>`_ for
organizing bug reports and feature requests.

The following `labels <https://github.com/pimutils/vdirsyncer/labels>`_ are of
interest:

* "Planning" is for issues that are still undecided, but where at least some
  discussion exists.

* "Blocked" is for issues that can't be worked on at the moment because some
  other unsolved problem exists. This problem may be a bug in some software
  dependency, for instance.

* "Ready" contains issues that are ready to work on.

All of those labels are also available as a kanban board on `waffles.io
<https://waffle.io/pimutils/vdirsyncer>`_. It is really just an alternative
overview over all issues, but might be easier to comprehend.

Feel free to :doc:`contact <contact>` me or comment on the relevant issues for
further information.

Reporting bugs
--------------

* Make sure your problem isn't already listed in :doc:`problems`.

* Make sure you have the latest version by executing ``pip install --user
  --upgrade vdirsyncer``.

* Use ``--verbosity=DEBUG`` when including output from vdirsyncer.

Suggesting features
-------------------

If you're suggesting a feature, keep in mind that vdirsyncer tries not to be a
full calendar or contacts client, but rather just the piece of software that
synchronizes all the data. :doc:`Take a look at the documentation for software
working with vdirsyncer <supported>`.

Submitting patches, pull requests
=================================

* **Discuss everything in the issue tracker first** (or contact me somehow
  else) before implementing it.

* Make sure the tests pass. See below for running them.

* But not because you wrote too few tests.

* Add yourself to ``AUTHORS.rst``, and add a note to ``CHANGELOG.rst`` too.

Running tests, how to set up your development environment
---------------------------------------------------------

For many patches, it might suffice to just let Travis run the tests. However,
Travis is slow, so you might want to run them locally too. For this, set up a
virtualenv_ and run this inside of it::

    make install-dev  # install vdirsyncer from the repo into the virtualenv
    make install-test  # install test dependencies
    make install-style  # install dependencies for stylechecking
    make install-docs  # install dependencies for building documentation

Then you can run::

    make test  # The normal testsuite
    make style  # Stylechecker
    make docs  # Build the HTML docs, output is at docs/_build/html/

If you have any questions, feel free to open issues about it.

.. _virtualenv: http://virtualenv.readthedocs.io/
