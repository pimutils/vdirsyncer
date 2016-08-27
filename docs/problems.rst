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
