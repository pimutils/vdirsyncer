=================
Storing passwords
=================

.. versionchanged:: 0.7.0

   Password configuration got completely overhauled.

Vdirsyncer can fetch passwords from a custom command or your system keyring if
the keyring_ Python package is installed.

Command
=======

Say you have the following configuration::

    [storage foo]
    type = caldav
    url = ...
    username = foo
    password = bar

But it bugs you that the password is stored in cleartext in the config file.
You can do this::

    [storage foo]
    type = caldav
    url = ...
    username = foo
    password.fetch = ["command", "~/get-password.sh", "more", "args"]

You can fetch the username as well::

    [storage foo]
    type = caldav
    url = ...
    username.fetch = ["command", "~/get-username.sh"]
    password.fetch = ["command", "~/get-password.sh"]

Or really any kind of parameter in a storage section.

System Keyring
==============

While the command approach is quite flexible, it is often cumbersome to write a
script fetching the system keyring.

Given that you have the keyring_ Python library installed, you can use::

    [storage foo]
    type = caldav
    username = myusername
    password.fetch = ["keyring", "myservicename", "myusername"]

.. _keyring: https://pypi.python.org/pypi/keyring
