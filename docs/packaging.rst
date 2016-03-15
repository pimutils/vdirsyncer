====================
Packaging guidelines
====================

Thank you very much for packaging vdirsyncer! The following guidelines should
help you to avoid some common pitfalls.

While they are called guidelines and therefore theoretically not mandatory, if
you consider going a different direction, please first open an issue or contact
me otherwise instead of just going ahead. These guidelines exist for my own
convenience too.

Obtaining the source code
=========================

The main distribution channel is `PyPI
<https://pypi.python.org/pypi/vdirsyncer>`_, and source tarballs can be
obtained there. Do not use the ones from GitHub: Their tarballs contain useless
junk and are more of a distraction than anything else.

I give each release a tag in the git repo. If you want to get notified of new
releases, `GitHub's feed
<https://github.com/pimutils/vdirsyncer/releases.atom>`_ is a good way.

Dependency versions
===================

It is strongly discouraged to package vdirsyncer as a Python 2 application.
Future releases will only work on Python 3.3 and newer versions.

As with most Python packages, ``setup.py`` denotes the runtime dependencies of
vdirsyncer. It also contains lower-bound versions of each dependency. Older
versions will be rejected by the testsuite.

Testing
=======

Everything testing-related goes through the ``Makefile`` in the root of the
repository or PyPI package. Trying to e.g. run ``py.test`` directly will
require a lot of environment variables to be set (for configuration) and you
probably don't want to deal with that.

You can install the testing dependencies with::

    make install-test

You probably don't want this since it will use pip to download the
dependencies. Alternatively you can find the testing dependencies in
``test-requirements.txt``, again with lower-bound version requirements.

You also have to have vdirsyncer fully installed at this point. Merely
``cd``-ing into the tarball will not be sufficient.

Running the tests happens with::

    make test

Hypothesis will randomly generate test input. If you care about deterministic
tests, set the ``DETERMINISTIC_TESTS`` variable to ``"true"``::

    make DETERMINISTIC_TESTS=true test

Documentation
=============

Using Sphinx_ you can generate the documentation you're reading right now in a
variety of formats, such as HTML, PDF, or even as a manpage. That said, I only
take care of the HTML docs' formatting.

You can find a list of dependencies in ``docs-requirements.txt``. Again, you
can install those using pip with::

    make install-docs

Then change into the ``docs/`` directory and build whatever format you want
using the ``Makefile`` in there (run ``make`` for the formats you can build).

.. _Sphinx: www.sphinx-doc.org/
