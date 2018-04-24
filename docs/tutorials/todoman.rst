=======
Todoman
=======

The iCalendar format also supports saving tasks in form of ``VTODO``-entries,
with the same file extension as normal events: ``.ics``. Many CalDAV servers
support synchronizing tasks, vdirsyncer does too.

todoman_ is a CLI task manager supporting :doc:`vdir </vdir>`. Its interface is
similar to the ones of Taskwarrior or the todo.txt CLI app. You can use
:storage:`filesystem` with it.

.. _todoman: http://todoman.readthedocs.io/

Setting up vdirsyncer
=====================

For this tutorial we will use NextCloud.

Assuming a config like this::

    [general]
    status_path = "~/.vdirsyncer/status/"

    [pair calendars]
    conflict_resolution = "b wins"
    a = "calendars_local"
    b = "calendars_dav"
    collections = ["from b"]
    metadata = ["color", "displayname"]

    [storage calendars_local]
    type = "filesystem"
    path = "~/.calendars/"
    fileext = ".ics"

    [storage calendars_dav]
    type = "caldav"
    url = "https://nextcloud.example.net/"
    username = "..."
    password = "..."

``vdirsyncer sync`` will then synchronize the calendars of your NextCloud_
instance to subfolders of ``~/.calendar/``.

.. _NextCloud: https://nextcloud.com/

Setting up todoman
==================

Write this to ``~/.config/todoman/todoman.conf``::

    [main]
    path = ~/.calendars/*

The glob_ pattern in ``path`` will match all subfolders in ``~/.calendars/``,
which is exactly the tasklists we want. Now you can use ``todoman`` as
described in its documentation_ and run ``vdirsyncer sync`` to synchronize the changes to NextCloud.

.. _glob: https://en.wikipedia.org/wiki/Glob_(programming)
.. _documentation: http://todoman.readthedocs.io/

Other clients
=============

The following client applications also synchronize over CalDAV:

- The Tasks-app found on iOS
- `OpenTasks for Android <https://github.com/dmfs/opentasks>`_
- The `Tasks <https://apps.nextcloud.com/apps/tasks>`_-app for NextCloud's web UI
