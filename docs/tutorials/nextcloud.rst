=========
nextCloud
=========

Vdirsyncer is continuously tested against the latest version of nextCloud_::

    [storage cal]
    type = "caldav"
    url = "https://nextcloud.example.com/"
    username = ...
    password = ...

    [storage card]
    type = "carddav"
    url = "https://nextcloud.example.com/"

- WebCAL-subscriptions can't be discovered by vdirsyncer. See `this relevant
  issue <https://github.com/nextcloud/calendar/issues/63>`_.

.. _nextCloud: https://nextcloud.com/
