==============
Known Problems
==============

For any unanswered questions or problems, see :doc:`contact`.

.. _debian-urllib3:

Requests-related ImportErrors
-----------------------------

    ImportError: No module named packages.urllib3.poolmanager

    ImportError: cannot import name iter_field_objects

Debian and nowadays even other distros make modifications to the ``requests``
package that don't play well with packages assuming a normal ``requests``. This
is due to stubbornness on both sides.

See :gh:`82` and :gh:`140` for past discussions. You have one option to work
around this, that is, to install vdirsyncer in a virtualenv, see
:ref:`manual-installation`.
