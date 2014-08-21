===============
Keyring Support
===============

*vdirsyncer* will try the following storages if no password (but a username) is
set in your config. If that fails too, it will prompt for the password and
store the password in the system keyring (if possible and wished).

netrc
=====

*vdirsyncer* can use ``~/.netrc`` for retrieving a password. An example
``.netrc`` looks like this::

    machine owncloud.example.com
    login foouser
    password foopass

System Keyring
==============

*vdirsyncer* can also use your system's password storage for saving password in
a (more) secure way.

To use it, you must install keyring_.

.. _keyring: https://bitbucket.org/kang/python-keyring-lib

*vdirsyncer* will use the hostname as key prefixed with ``vdirsyncer:`` when
saving and fetching, e.g. ``vdirsyncer:owncloud.example.com``.

*keyring* support these keyrings:

 - **OSXKeychain:** The Keychain service in Mac OS X.
 - **KDEKWallet:** The KDE's Kwallet service.
 - **GnomeKeyring** For Gnome 2 environment.
 - **SecretServiceKeyring:** For newer GNOME and KDE environments.
 - **WinVaultKeyring:** The Windows Credential Vault
 - **Win32CryptoKeyring:** for Windows 2k+.
 - **CryptedFileKeyring:** A command line interface keyring base on PyCrypto.
 - **UncryptedFileKeyring:** A keyring which leaves passwords directly in file.

Changing the Password
---------------------

If your password on the server changed or you misspelled it you need to use
your system's password manager (e.g. seahorse for most Linux distrubutions) to
either delete or directly change it, *vdirsyncer* currently has no means to do
it for you.
