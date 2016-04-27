==============
Known Problems
==============

For any unanswered questions or problems, see :doc:`contact`.

.. _debian-urllib3:

Requests-related ImportErrors on Debian-based distributions
-----------------------------------------------------------

    ImportError: No module named packages.urllib3.poolmanager

    ImportError: cannot import name iter_field_objects

Debian has had its problems in the past with the Python requests package, see
:gh:`82` and :gh:`140`. You have several options for solving this problem:

- Set the ``auth`` parameter of :storage:`caldav`, :storage:`carddav`, and/or
  :storage:`http` to ``basic`` or ``digest`` (not ``guess``).

- Upgrade your installation of the Debian requests package to at least version
  ``2.4.3-1``.

- If this doesn't help, install vdirsyncer in a virtualenv, see
  :ref:`manual-installation`.


.. _manual-installation:

Manual installation
-------------------

If your distribution doesn't provide a package for vdirsyncer, you still can
use Python's package manager "pip". First, you'll have to check that the
following things are installed:

- A compatible version of Python (2.7+ or 3.3+) and the corresponding pip package
- ``libxml`` and ``libxslt``
- ``zlib``

On Linux systems, using the distro's package manager is the best
way to do this, for example, using Ubuntu::

    sudo apt-get install libxml2 libxslt1.1 zlib1g python

Then you have several options:

The dirty, easy way
~~~~~~~~~~~~~~~~~~~

The easiest way to install vdirsyncer at this point would be to run::

    pip install --user vdirsyncer

This method has a major flaw though: Pip doesn't keep track of the files it
installs. Vdirsyncer's files would be located somewhere in
``~/.local/lib/python*``, but you can't possibly know which packages were
installed as dependencies of vdirsyncer and which ones were not, should you
decide to uninstall it. In other words, using pip that way would pollute your
home directory.

The clean but hard way
~~~~~~~~~~~~~~~~~~~~~~

There is a way to install Python software without scattering stuff across
your filesystem: virtualenv_. There are a lot of resources on how to use it,
the simplest possible way would look something like::

    virtualenv ~/vdirsyncer_env
    ~/vdirsyncer_env/bin/pip install vdirsyncer
    alias vdirsyncer="~/vdirsyncer_env/bin/vdirsyncer

You'll have to put the last line into your ``.bashrc`` or ``.bash_profile``.

This method has two advantages:

- It separately installs all Python packages into ``~/vdirsyncer_env/``,
  without relying on the system packages. This works around OS- or
  distro-specific issues.
- You can delete ``~/vdirsyncer_env/`` to uninstall vdirsyncer entirely.

The new, perfect way
~~~~~~~~~~~~~~~~~~~~

pipsi_ is a new package manager for Python-based software that automatically
sets up a virtualenv for each program you install. Assuming you have it
installed on your operating system, you can do::

    pipsi install --python python3 vdirsyncer

and ``.local/bin/vdirsyncer`` will be your new vdirsyncer installation. To
update vdirsyncer to the latest version::

    pipsi upgrade vdirsyncer

If you're done with vdirsyncer, you can do::

    pipsi uninstall vdirsyncer

and vdirsyncer will be uninstalled, including its dependencies.

.. _virtualenv: https://virtualenv.readthedocs.io/
.. _pipsi: https://github.com/mitsuhiko/pipsi
