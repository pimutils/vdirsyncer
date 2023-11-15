.. _installation:

============
Installation
============

OS/distro packages
------------------

The following packages are community-contributed and were up-to-date at the
time of writing:

- `Arch Linux <https://archlinux.org/packages/extra/any/vdirsyncer/>`_
- `Ubuntu and Debian, x86_64-only
  <https://packagecloud.io/pimutils/vdirsyncer>`_ (packages also exist
  in the official repositories but may be out of date)
- `GNU Guix <https://packages.guix.gnu.org/packages/vdirsyncer/>`_
- `macOS (homebrew) <https://formulae.brew.sh/formula/vdirsyncer>`_
- `NetBSD <https://ftp.netbsd.org/pub/pkgsrc/current/pkgsrc/time/py-vdirsyncer/index.html>`_
- `OpenBSD <http://ports.su/productivity/vdirsyncer>`_
- `Slackware (SlackBuild at Slackbuilds.org) <https://slackbuilds.org/repository/15.0/network/vdirsyncer/>`_

We only support the latest version of vdirsyncer, which is at the time of this
writing |vdirsyncer_version|. Please **do not file bugs if you use an older
version**.

Some distributions have multiple release channels. Debian and Fedora for
example have a "stable" release channel that ships an older version of
vdirsyncer. Those versions aren't supported either.

If there is no suitable package for your distribution, you'll need to
:ref:`install vdirsyncer manually <manual-installation>`. There is an easy
command to copy-and-paste for this as well, but you should be aware of its
consequences.

.. _manual-installation:

Manual installation
-------------------

If your distribution doesn't provide a package for vdirsyncer, you still can
use Python's package manager "pip". First, you'll have to check that the
following things are installed:

- Python 3.7 to 3.11 and pip.
- ``libxml`` and ``libxslt``
- ``zlib``
- Linux or macOS. **Windows is not supported**, see :gh:`535`.

On Linux systems, using the distro's package manager is the best
way to do this, for example, using Ubuntu::

    sudo apt-get install libxml2 libxslt1.1 zlib1g python3

Then you have several options. The following text applies for most Python
software by the way.

pipx: The clean, easy way
~~~~~~~~~~~~~~~~~~~~~~~~~

pipx_ is a new package manager for Python-based software that automatically
sets up a virtual environment for each program it installs. Please note that
installing via pipx will not include manual pages nor systemd services.

pipx will install vdirsyncer into ``~/.local/pipx/venvs/vdirsyncer``

Assuming that pipx is installed, vdirsyncer can be installed with::

    pipx install vdirsyncer

It can later be updated to the latest version with::

    pipx upgrade vdirsyncer

And can be uninstalled with::

    pipx uninstall vdirsyncer

This last command will remove vdirsyncer and any dependencies installed into
the above location.

.. _pipx: https://github.com/pipxproject/pipx

The dirty, easy way
~~~~~~~~~~~~~~~~~~~

If pipx is not available on your distirbution, the easiest way to install
vdirsyncer at this point would be to run::

    pip install --ignore-installed vdirsyncer

- ``--ignore-installed`` is to work around Debian's potentially broken packages
  (see :ref:`debian-urllib3`).

This method has a major flaw though: Pip doesn't keep track of the files it
installs. Vdirsyncer's files would be located somewhere in
``~/.local/lib/python*``, but you can't possibly know which packages were
installed as dependencies of vdirsyncer and which ones were not, should you
decide to uninstall it. In other words, using pip that way would pollute your
home directory.

The clean, hard way
~~~~~~~~~~~~~~~~~~~

There is a way to install Python software without scattering stuff across
your filesystem: virtualenv_. There are a lot of resources on how to use it,
the simplest possible way would look something like::

    virtualenv ~/vdirsyncer_env
    ~/vdirsyncer_env/bin/pip install vdirsyncer
    alias vdirsyncer="~/vdirsyncer_env/bin/vdirsyncer"

You'll have to put the last line into your ``.bashrc`` or ``.bash_profile``.

This method has two advantages:

- It separately installs all Python packages into ``~/vdirsyncer_env/``,
  without relying on the system packages. This works around OS- or
  distro-specific issues.
- You can delete ``~/vdirsyncer_env/`` to uninstall vdirsyncer entirely.

.. _virtualenv: https://virtualenv.readthedocs.io/
