==============
Server Support
==============

vdirsyncer is currently regularly and automatically tested against the latest
versions of Radicale and ownCloud. In principle, vdirsyncer is supposed to run
correctly with any remotely popular CalDAV or CardDAV server. 

vdirsyncer's synchronization works best if the items have ``UID`` properties.
Items which don't have this property still should be synchronized fine as of
version 1.5, but for performance reasons, such items should rather be the
exception than the rule. For a possible way to automatically fix such items,
take a look at `vfix <https://github.com/geier/vfix>`_.

Radicale
========

Vdirsyncer is tested against the git version and the latest PyPI release of
Radicale.

- Radicale doesn't `support time ranges in the calendar-query of CalDAV
  <https://github.com/Kozea/Radicale/issues/146>`_, so setting ``start_date``
  and ``end_date`` for :py:class:`vdirsyncer.storage.CaldavStorage` will have
  no or unpredicted consequences.

- `Versions of Radicale older than 0.9b1 choke on RFC-conform queries for all
  items of a collection <https://github.com/Kozea/Radicale/issues/143>`_.

  Vdirsyncer's default value ``'VTODO, VEVENT'`` for
  :py:class:`vdirsyncer.storage.CaldavStorage`'s ``item_types`` parameter will
  work fine with these versions, and so will all values, except for the empty
  one.

  The empty value ``''`` will get vdirsyncer to send a single HTTP request to
  fetch all items, instead of one HTTP request for each possible item type. As
  the linked issue describes, old versions of Radicale expect a
  non-RFC-compliant format for such queries, one which vdirsyncer doesn't
  support.

ownCloud
========

Vdirsyncer is tested against the latest version of ownCloud.

- *Versions older than 7.0.0:* ownCloud uses SabreDAV, which had problems
  detecting collisions and race-conditions. The problems were reported and are
  fixed in SabreDAV's repo, and the corresponding fix is also in ownCloud since
  7.0.0. See `Bug #16 <https://github.com/untitaker/vdirsyncer/issues/16>`_ for
  more information.
