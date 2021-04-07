============================
Contributing to this project
============================

.. note::

    - Please read :doc:`contact` for questions and support requests.

    - All participants must follow the `pimutils Code of Conduct
      <http://pimutils.org/coc>`_.

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

If you just want to get started with contributing, the "ready" issues are an
option. Issues that are still in "Planning" are also an option, but require
more upfront thinking and may turn out to be impossible to solve, or at least
harder than anticipated. On the flip side those tend to be the more interesting
issues as well, depending on how one looks at it.

All of those labels are also available as a kanban board on `waffle.io
<https://waffle.io/pimutils/vdirsyncer>`_. It is really just an alternative
overview over all issues, but might be easier to comprehend.

Feel free to :doc:`contact <contact>` me or comment on the relevant issues for
further information.

Reporting bugs
--------------

* Make sure your problem isn't already listed in :doc:`problems`.

* Make sure you have the absolutely latest version of vdirsyncer. For users of
  some Linux distributions such as Debian or Fedora this may not be the version
  that your distro offers. In those cases please file a bug against the distro
  package, not against upstream vdirsyncer.

* Use ``--verbosity=DEBUG`` when including output from vdirsyncer.

Suggesting features
-------------------

If you're suggesting a feature, keep in mind that vdirsyncer tries not to be a
full calendar or contacts client, but rather just the piece of software that
synchronizes all the data. :doc:`Take a look at the documentation for software
working with vdirsyncer <tutorials/index>`.

Submitting patches, pull requests
=================================

* **Discuss everything in the issue tracker first** (or contact me somehow
  else) before implementing it.

* Make sure the tests pass. See below for running them.

* But not because you wrote too few tests.

* Add yourself to ``AUTHORS.rst``, and add a note to ``CHANGELOG.rst`` too.

Running tests, how to set up your development environment
---------------------------------------------------------

For many patches, it might suffice to just let CI run the tests. However,
CI is slow, so you might want to run them locally too. For this, set up a
virtualenv_ and run this inside of it::

    # install:
    #  - vdirsyncer from the repo into the virtualenv
    #  - stylecheckers (flake8) and code formatters (autopep8)
    make install-dev

    # Install git commit hook for some extra linting and checking
    pre-commit install

    # install test dependencies
    make install-test

Then you can run::

    make test   # The normal testsuite
    make style  # Stylechecker
    make docs   # Build the HTML docs, output is at docs/_build/html/

The ``Makefile`` has a lot of options that allow you to control which tests are
run, and which servers are tested. Take a look at its code where they are all
initialized and documented.

For example, to test xandikos, first run the server itself::

    docker build -t xandikos docker/xandikos
    docker start -p 8000:8000 xandikos

Then run the tests specifying this ``DAV_SERVER``, run::

    make DAV_SERVER=xandikos test

If you have any questions, feel free to open issues about it.

Structure of the testsuite
--------------------------

Within ``tests/``, there are three main folders:

- ``system`` contains system- and also integration tests. A rough rule is: If
  the test is using temporary files, put it here.

- ``unit``, where each testcase tests a single class or function.

- ``storage`` runs a generic storage testsuite against all storages.

The reason for this separation is: We are planning to generate separate
coverage reports for each of those testsuites. Ideally ``unit`` would generate
palatable coverage of the entire codebase *on its own*, and the *combination*
of ``system`` and ``storage`` as well.

.. _virtualenv: http://virtualenv.readthedocs.io/
