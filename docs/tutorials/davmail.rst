.. _davmail_setup:

===========================
DavMail (Exchange, Outlook)
===========================

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
