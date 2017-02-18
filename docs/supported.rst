==================
Supported Software
==================

Client applications
===================

The following software has been reported to work well with vdirsyncer, however,
none of it is regularly tested.

Calendars
---------

- khal_, a CLI calendar application supporting :doc:`vdir <vdir>`. You can use
  :storage:`filesystem` with it.

- Many graphical calendar apps such as dayplanner_, Orage_ or rainlendar_ save
  a calendar in a single ``.ics`` file. You can use :storage:`singlefile` with
  those.

.. _khal: http://lostpackets.de/khal/
.. _dayplanner: http://www.day-planner.org/
.. _Orage: http://www.kolumbus.fi/~w408237/orage/
.. _rainlendar: http://www.rainlendar.net/

Task/Todo managers
------------------

The iCalendar format also supports saving tasks in form of ``VTODO``-entries,
with the same file extension as normal events: ``.ics``. All CalDAV servers
support synchronizing tasks, vdirsyncer does too.

- todoman_, a CLI task manager supporting :doc:`vdir <vdir>`.  You can use
  :storage:`filesystem` with it.

  Its interface is similar to the ones of Taskwarrior or the todo.txt CLI app
  and should be intuitively usable.

.. _todoman: https://hugo.barrera.io/journal/2015/03/30/introducing-todoman/


Contacts
--------

- khard_, a commandline addressbook supporting :doc:`vdir <vdir>`.  You can use
  :storage:`filesystem` with it.

- contactquery.c_, a small program explicitly written for querying vdirs from
  mutt.

- mates_, a commandline addressbook supporting :doc:`vdir <vdir>`.

- vdirel_, access :doc:`vdir <vdir>` contacts from Emacs.

.. _khard: https://github.com/scheibler/khard/
.. _contactquery.c: https://github.com/t-8ch/snippets/blob/master/contactquery.c
.. _mates: https://github.com/untitaker/mates.rs
.. _vdirel: https://github.com/DamienCassou/vdirel

.. _supported-servers:

Supported servers
=================

CalDAV and CardDAV servers not listed here may work anyway.

Radicale
--------

Radicale_ is a very lightweight server, however, it intentionally doesn't
implement the CalDAV and CardDAV standards completely, which might lead to
issues even with very well-written clients. Apart from its non-conformity with
standards, there are multiple other problems with its code quality and the way
it is maintained.

That said, vdirsyncer is continuously tested against the git version and the
latest PyPI release of Radicale.

- Vdirsyncer can't create collections on Radicale.
- Radicale doesn't `support time ranges in the calendar-query of CalDAV
  <https://github.com/Kozea/Radicale/issues/146>`_, so setting ``start_date``
  and ``end_date`` for :storage:`caldav` will have no or unpredicted
  consequences.

- `Versions of Radicale older than 0.9b1 choke on RFC-conform queries for all
  items of a collection <https://github.com/Kozea/Radicale/issues/143>`_.

  You have to set ``item_types = ["VTODO", "VEVENT"]`` in
  :storage:`caldav` for vdirsyncer to work with those versions.

.. _Radicale: http://radicale.org/


.. _owncloud_setup:

ownCloud
--------

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

nextCloud
---------

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


FastMail
--------

Vdirsyncer is irregularly tested against FastMail_. There are no known issues
with it. `FastMail's support pages
<https://www.fastmail.com/help/technical/servernamesandports.html>`_ provide
the settings to use::

    [storage cal]
    type = "caldav"
    url = "https://caldav.messagingengine.com/"
    username = ...
    password = ...

    [storage card]
    type = "carddav"
    url = "https://carddav.messagingengine.com/"
    username = ...
    password = ...

.. _FastMail: https://www.fastmail.com/

.. _icloud_setup:

iCloud
------

Vdirsyncer is irregularly tested against iCloud_.

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
- Vdirsyncer can't create collections on iCloud.

.. _iCloud: https://www.icloud.com/

.. _davmail_setup:

DavMail (Exchange, Outlook)
---------------------------

DavMail_ is a proxy program that allows you to use Card- and CalDAV clients
with Outlook. That allows you to use vdirsyncer with Outlook.

In practice your success with DavMail may wildly vary. Depending on your
Exchange server you might get confronted with weird errors of all sorts
(including data-loss).

**Make absolutely sure you use the latest DavMail**::

    [storage outlook]
    type = "caldav"
    url = "http://localhost:1080/users/user@example.com/calendar/"
    username = "user@example.com"
    password = ...

- Older versions of DavMail handle URLs case-insensitively. See :gh:`144`.
- DavMail is handling malformed data on the Exchange server very poorly. In
  such cases the `Calendar Checking Tool for Outlook
  <https://www.microsoft.com/en-us/download/details.aspx?id=28786>`_ might
  help.
- In some cases, you may see errors about duplicate events. It may look
  something like this::

      error: my_calendar/calendar: Storage "my_calendar_remote/calendar" contains multiple items with the same UID or even content. Vdirsyncer will now abort the synchronization of this collection, because the fix for this is not clear; It could be the result of a badly behaving server. You can try running:
      error:
      error:     vdirsyncer repair my_calendar_remote/calendar
      error:
      error: But make sure to have a backup of your data in some form. The offending hrefs are:
      [...]

  In order to fix this, you can try the Remove-DuplicateAppointments.ps1_
  PowerShell script that Microsoft has come up with in order to remove duplicates.

.. _DavMail: http://davmail.sourceforge.net/
.. _Remove-DuplicateAppointments.ps1: https://blogs.msdn.microsoft.com/emeamsgdev/2015/02/12/powershell-remove-duplicate-calendar-appointments/

Baikal
------

Vdirsyncer is continuously tested against the latest version of Baikal_.

- Baikal up to ``0.2.7`` also uses an old version of SabreDAV, with the same
  issue as ownCloud, see :gh:`160`. This issue is fixed in later versions.

.. _Baikal: http://baikal-server.com/

Google
------

Using vdirsyncer with Google Calendar is possible as of 0.10, but it is not
tested frequently. You can use :storage:`google_contacts` and
:storage:`google_calendar`.

For more information see :gh:`202` and :gh:`8`.
