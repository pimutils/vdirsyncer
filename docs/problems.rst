==========================
Support and Known Problems
==========================

For any unanswered questions or problems, `open an issue on GitHub
<https://github.com/untitaker/vdirsyncer/issues/new>`_ or `contact me directly
<https://unterwaditzer.net>`_.

Error messages
--------------

- **[Errno 185090050] _ssl.c:343: error:0B084002:x509 certificate
  routines:X509_load_cert_crl_file:system lib**

  vdirsyncer cannot find the path to your certificate bundle, you need to
  supply it as a parameter to ``verify`` in storage configuration, e.g.::

      verify = /usr/share/ca-certificates/cacert.org/cacert.org_root.crt

- **ImportError: No module named packages.urllib3.poolmanager**

  This happens if the requests package was installed via Debian's package
  manager, see :gh:`82`. You have two options for solving this problem:

  - Upgrade your installation of the Debian requests package to at least
    version ``2.4.3-1``.

  - Install vdirsyncer in a virtualenv, see :ref:`manual-installation`.


.. _manual-installation:

Manual installation
-------------------

If your distribution doesn't provide a package for vdirsyncer, you still can
use Python's package manager "pip". First, you'll have to check that a
compatible version of Python (2.7+ or 3.3+) and the corresponding pip package
are installed. On Linux systems, using the distro's package manager is the best
way to do this.

The easiest way to install vdirsyncer at this point would be to run::

    pip install --user vdirsyncer

This method has a major flaw though: Pip doesn't keep track of the files it
installs.  Vdirsyncer's files would be located somewhere in
``~/.local/lib/python*``, but you can't possibly know which packages were
installed as dependencies of vdirsyncer and which ones were not, should you
decide to uninstall it. In other words, using pip that way would pollute your
home directory.

But there is a way to install Python software without scattering stuff across
your filesystem: virtualenv_. There are a lot of resources on how to use it,
the simplest possible way would look something like::

    virtualenv ~/vdirsyncer_env
    ~/vdirsyncer_env/bin/pip install vdirsyncer
    alias vdirsyncer="~/vdirsyncer_env/bin/vdirsyncer

You'll have to put the last line into your ``.bashrc`` or ``.bash_profile``.
The main advantage is that you can delete the ``~/vdirsyncer_env`` folder to
uninstall vdirsyncer. Also, pipsi_ is a relatively new tool which tries to
automate this process in a end-user friendly way.

.. _virtualenv: https://virtualenv.readthedocs.org/
.. _pipsi: https://github.com/mitsuhiko/pipsi
