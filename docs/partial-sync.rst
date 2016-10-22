.. _partial_sync_tutorial:

===============================
Syncing with read-only storages
===============================

If you want to subscribe to a public, read-only `WebCAL
<https://en.wikipedia.org/wiki/Webcal>`_-calendar but neither your server nor
your calendar apps support that (or support it insufficiently), vdirsyncer can
be used to synchronize such a public calendar ``A`` with a new calendar ``B``
of your own and keep ``B`` updated.

Step 1: Create the target calendar
==================================

First you need to create the calendar you want to sync the WebCAL-calendar
with. Most servers offer a web interface for this. You then need to note the
CalDAV URL of your calendar. Note that this URL should directly point to the
calendar you just created, which means you would have one such URL for each
calendar you have.

Step 2: Creating the config
===========================

Paste this into your vdirsyncer config::

    [pair holidays]
    a = "holidays_public"
    b = "holidays_private"
    collections = null

    [storage holidays_public]
    type = "http"
    # The URL to your iCalendar file.
    url = ...

    [storage holidays_private]
    type = "caldav"
    # The direct URL to your calendar.
    url = ...
    # The credentials to your CalDAV server
    username = ...
    password = ...

Then run ``vdirsyncer discover holidays`` and ``vdirsyncer sync holidays``, and
your previously created calendar should be filled with events.

Step 3: The partial_sync parameter
==================================

.. versionadded:: 0.14

You may get into a situation where you want to hide or modify some events from
your ``holidays`` calendar. If you try to do that at this point, you'll notice
that vdirsyncer will revert any changes you've made after a few times of
running ``sync``. This is because vdirsyncer wants to keep everything in sync,
and it can't synchronize changes to the public holidays-calendar because it
doesn't have the rights to do so.

For such purposes you can set the ``partial_sync`` parameter to ``ignore``::

    [pair holidays]
    a = "holidays_public"
    b = "holidays_private"
    collections = null
    partial_sync = ignore

See :ref:`the config docs <partial_sync_def>` for more information.

.. _nextCloud: https://nextcloud.com/
.. _Baikal: http://sabre.io/baikal/
.. _DAViCal: http://www.davical.org/
