.. _installation:

============
Installation
============

OS/distro packages
------------------

Unless you want to contribute to vdirsyncer, you should use the packages from
your distribution:

- `ArchLinux (AUR) <https://aur.archlinux.org/packages/vdirsyncer>`_
- `pkgsrc <http://pkgsrc.se/time/py-vdirsyncer>`_
- `Fedora <https://apps.fedoraproject.org/packages/vdirsyncer>`_
- `nixpkg <https://github.com/NixOS/nixpkgs/tree/master/pkgs/tools/misc/vdirsyncer>`_
- `GNU Guix <https://www.gnu.org/software/guix/package-list.html#vdirsyncer>`_
- `homebrew <http://braumeister.org/formula/vdirsyncer>`_
- `Gentoo <https://packages.gentoo.org/packages/dev-python/vdirsyncer>`_
- `Debian Sid <https://packages.debian.org/search?keywords=vdirsyncer&searchon=names&exact=1&suite=all&section=all>`_.
- Debian stable and Ubuntu don't have packages, but make a manual installation
  especially hard. See :ref:`debian-urllib3`.

If there is no package for your distribution, you'll need to :ref:`install
vdirsyncer manually <manual-installation>`. There is an easy command to
copy-and-paste for this as well, but you should be aware of its consequences.


.. _manual-installation:

Manual installation
-------------------

If your distribution doesn't provide a package for vdirsyncer, you still can
use Python's package manager "pip". First, you'll have to check that the
following things are installed:

- Python 3.3+ and pip.
- ``libxml`` and ``libxslt``
- ``zlib``

On Linux systems, using the distro's package manager is the best
way to do this, for example, using Ubuntu::

    sudo apt-get install libxml2 libxslt1.1 zlib1g python

Then you have several options. The following text applies for most Python
software by the way.

The dirty, easy way
~~~~~~~~~~~~~~~~~~~

The easiest way to install vdirsyncer at this point would be to run::

    pip install --user --ignore-installed vdirsyncer

- ``--user`` is to install without root rights (into your home directory)
- ``--ignore-installed`` is to work around Debian's potentially broken packages
  (see :ref:`debian-urllib3`).

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
