.. _owncloud_setup:

========
ownCloud
========

Vdirsyncer is continuously tested against the latest version of ownCloud_::

    [storage cal]
    type = "caldav"
    url = "https://example.com/remote.php/dav/"
    username = ...
    password = ...

    [storage card]
    type = "carddav"
    url = "https://example.com/remote.php/dav/"
    username = ...
    password = ...

- *Versions older than 7.0.0:* ownCloud uses SabreDAV, which had problems
  detecting collisions and race-conditions. The problems were reported and are
  fixed in SabreDAV's repo, and the corresponding fix is also in ownCloud since
  7.0.0. See :gh:`16` for more information.

.. _ownCloud: https://owncloud.org/
