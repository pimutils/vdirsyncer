==================
Supported Software
==================

Client applications
===================

The following software has been reported to work well with vdirsyncer, however,
none of it is regularly tested.

Calendars
---------

- `khal <http://lostpackets.de/khal/>`_, a CLI calendar application supporting
  :doc:`vdir <vdir>`. You can use
  :py:class:`vdirsyncer.storage.FilesystemStorage` with it.

- Many graphical calendar apps such as dayplanner_, Orage_ or rainlendar_ save
  a calendar in a single ``.ics`` file. You can use
  :py:class:`vdirsyncer.storage.SingleFileStorage` with those.

.. _dayplanner: http://www.day-planner.org/
.. _Orage: http://www.kolumbus.fi/~w408237/orage/
.. _rainlendar: http://www.rainlendar.net/

Contacts
--------

- `khard <http://github.com/scheibler/khard/>`_, a commandline addressbook
  supporting :doc:`vdir <vdir>`. You can use
  :py:class:`vdirsyncer.storage.FilesystemStorage` with it.

- `The ppl addressbook <http://ppladdressbook.org/>`_ uses a storage format
  similar to :doc:`vdir <vdir>`. There are some pitfalls though, `see the notes
  on the related issue <https://github.com/hnrysmth/ppl/issues/47>`_.

- `contactquery.c <https://github.com/t-8ch/snippets/blob/master/contactquery.c>`_,
  a small program explicitly written for querying vdirs from mutt.

Supported servers
=================

CalDAV and CardDAV servers not listed here may work anyway.

Radicale
--------

Vdirsyncer is continuously tested against the git version and the latest PyPI
release of Radicale_. Older versions have substantial deficiencies, and using
them is neither supported nor encouraged.

- Radicale doesn't `support time ranges in the calendar-query of CalDAV
  <https://github.com/Kozea/Radicale/issues/146>`_, so setting ``start_date``
  and ``end_date`` for :py:class:`vdirsyncer.storage.CaldavStorage` will have
  no or unpredicted consequences.

- `Versions of Radicale older than 0.9b1 choke on RFC-conform queries for all
  items of a collection <https://github.com/Kozea/Radicale/issues/143>`_.

  Vdirsyncer's default value ``["VTODO", "VEVENT"]'`` for
  :py:class:`vdirsyncer.storage.CaldavStorage`'s ``item_types`` parameter will
  work fine with these versions, and so will all values, except for the empty
  one.

  The empty list ``[]`` will get vdirsyncer to send a single HTTP request to
  fetch all items, instead of one HTTP request for each possible item type. As
  the linked issue describes, old versions of Radicale expect a
  non-RFC-compliant format for such queries, one which vdirsyncer doesn't
  support.

.. _Radicale: http://radicale.org/

ownCloud
--------

Vdirsyncer is continuously tested against the latest version of ownCloud_.

- *Versions older than 7.0.0:* ownCloud uses SabreDAV, which had problems
  detecting collisions and race-conditions. The problems were reported and are
  fixed in SabreDAV's repo, and the corresponding fix is also in ownCloud since
  7.0.0. See :gh:`16` for more information.

.. _ownCloud: https://owncloud.org/

FastMail
--------

Vdirsyncer is irregularly tested against FastMail_. There are no known issues
with it.

.. _FastMail: https://www.fastmail.com/

iCloud
------

Vdirsyncer is irregularly tested against iCloud_. There are no known issues
with it.

.. _iCloud: http://icloud.com/

DavMail (Exchange, Outlook)
---------------------------

Using vdirsyncer with DavMail_ is currently not recommended (if even possible).

- DavMail (or the server it is proxying) handles URLs case-insensitively. See
  :gh:`144`.

.. _DavMail: http://davmail.sourceforge.net/

Baikal
------

Vdirsyncer is continuously tested against the latest version of Baikal_.

- Baikal up to ``0.2.7`` also uses an old version of SabreDAV, with the same issue as
  ownCloud, see :gh:`160`.

.. _Baikal: http://baikal-server.com/
