====================
Packaging guidelines
====================

Thank you very much for packaging vdirsyncer! The following guidelines should
help you to avoid some common pitfalls.

If you find yourself needing to patch anything, or going in a different direction,
please open an issue so we can also address in a way that works for everyone. Otherwise
we get bug reports for code or scenarios that don't exist in upstream vdirsycner.

Obtaining the source code
=========================

The main distribution channel is `PyPI
<https://pypi.python.org/pypi/vdirsyncer>`_, and source tarballs can be
obtained there. We mirror the same package tarball and wheel as GitHub
releases. Please do not confuse these with the auto-generated GitHub "Source
Code" tarball. Those are missing some important metadata and your build will fail.

We give each release a tag in the git repo. If you want to get notified of new
releases, `GitHub's feed
<https://github.com/pimutils/vdirsyncer/releases.atom>`_ is a good way.

Tags will be signed by the maintainer who is doing the release (starting with
0.16.8), and generation of the tarball and wheel is done by CI. Hence, only the
tag itself is signed.

Dependency versions
===================

As with most Python packages, ``setup.py`` denotes the dependencies of
vdirsyncer. It also contains lower-bound versions of each dependency. Older
versions will be rejected by the testsuite.

Testing
=======

Everything testing-related goes through the ``Makefile`` in the root of the
repository or PyPI package. Trying to e.g. run ``pytest`` directly will
require a lot of environment variables to be set (for configuration) and you
probably don't want to deal with that.

You can install the all development dependencies with::

    make install-dev

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

There are a lot of additional variables that allow you to test vdirsyncer
against a particular server. Those variables are not "stable" and may change
drastically between minor versions. Just don't use them, you are unlikely to
find bugs that vdirsyncer's CI hasn't found.

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

Contrib files
=============

Reference ``systemd.service`` and ``systemd.timer`` unit files are provided. It
is recommended to install this if your distribution is systemd-based.
