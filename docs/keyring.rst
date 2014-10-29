===============
Keyring Support
===============

Vdirsyncer will try the following storages in that order if no password (but a
username) is set in your config. If all of those methods fail, it will prompt
for the password and store the password in the system keyring (if possible and
wished).

Custom command
==============

.. versionadded:: 0.3.0

A custom command/binary can be specified to retrieve the password for a
username/hostname combination. See :ref:`general_config`.

netrc
=====

Vdirsyncer can use ``~/.netrc`` for retrieving a password. An example
``.netrc`` looks like this::

    machine owncloud.example.com
    login foouser
    password foopass

System Keyring
==============

Vdirsyncer can use your system's password storage, utilizing the keyring_
library. Supported services include **OS X Keychain, Gnome Keyring, KDE Kwallet
or the Windows Credential Vault**. For a full list see the library's
documentation.

To use it, you must install the ``keyring`` Python package.

.. _keyring: https://bitbucket.org/kang/python-keyring-lib

Storing the password
--------------------

Vdirsyncer will use the hostname as key prefixed with ``vdirsyncer:``, e.g.
``vdirsyncer:owncloud.example.com``.

Changing the Password
---------------------

If your password on the server changed or you misspelled it, you need to
manually edit or delete the entry in your system keyring.
