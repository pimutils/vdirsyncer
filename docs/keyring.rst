=================
Storing passwords
=================

.. versionchanged:: 0.7.0

   Password configuration got completely overhauled.

Vdirsyncer can fetch passwords from several sources other than the config file.

Command
=======

Say you have the following configuration::

    [storage foo]
    type = "caldav"
    url = ...
    username = "foo"
    password = "bar"

But it bugs you that the password is stored in cleartext in the config file.
You can do this::

    [storage foo]
    type = "caldav"
    url = ...
    username = "foo"
    password.fetch = ["command", "~/get-password.sh", "more", "args"]

You can fetch the username as well::

    [storage foo]
    type = "caldav"
    url = ...
    username.fetch = ["command", "~/get-username.sh"]
    password.fetch = ["command", "~/get-password.sh"]

Or really any kind of parameter in a storage section.

You can also pass the command as a string to be executed in a shell::

    [storage foo]
    ...
    password.fetch = ["shell", "~/.local/bin/get-my-password | head -n1"]

With pass_ for example, you might find yourself writing something like this in
your configuration file::

    password.fetch = ["command", "pass", "caldav"]

.. _pass: https://www.passwordstore.org/

Accessing the system keyring
----------------------------

As shown above, you can use the ``command`` strategy to fetch your credentials
from arbitrary sources. A very common usecase is to fetch your password from
the system keyring.

The keyring_ Python package contains a command-line utility for fetching
passwords from the OS's password store. Installation::

    pip install keyring

Basic usage::

    password.fetch = ["command", "keyring", "get", "example.com", "foouser"]

.. _keyring: https://github.com/jaraco/keyring/

Password Prompt
===============

You can also simply prompt for the password::

    [storage foo]
    type = "caldav"
    username = "myusername"
    password.fetch = ["prompt", "Password for CalDAV"]

Environment variable
===============

To read the password from an environment variable::

    [storage foo]
    type = "caldav"
    username = "myusername"
    password.fetch = ["command", "printenv", "DAV_PW"]

This is especially handy if you use the same password multiple times
(say, for a CardDAV and a CalDAV storage).
On bash, you can read and export the password without printing::

    read -s DAV_PW "DAV Password: " && export DAV_PW
