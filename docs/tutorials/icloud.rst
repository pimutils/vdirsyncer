.. _icloud_setup:

======
iCloud
======

Vdirsyncer is tested against iCloud_.

.. note::

    Automated testing against iCloud is broken! See :gh:`646`.

::

    [storage cal]
    type = "caldav"
    url = "https://caldav.icloud.com/"
    username = ...
    password = ...

    [storage card]
    type = "carddav"
    url = "https://contacts.icloud.com/"
    username = ...
    password = ...

Problems:

- Vdirsyncer can't do two-factor auth with iCloud (there doesn't seem to be a
  way to do two-factor auth over the DAV APIs) You'll need to use `app-specific
  passwords <https://support.apple.com/en-us/HT204397>`_ instead.
- iCloud has a few special requirements when creating collections. In principle
  vdirsyncer can do it, but it is recommended to create them from an Apple
  client (or the iCloud web interface).

  - iCloud requires a minimum length of collection names.
  - Calendars created by vdirsyncer cannot be used as tasklists.

.. _iCloud: https://www.icloud.com/
