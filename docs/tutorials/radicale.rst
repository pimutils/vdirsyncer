========
Radicale
========

Radicale_ is a very lightweight server, however, it intentionally doesn't
implement the CalDAV and CardDAV standards completely, which might lead to
issues even with very well-written clients. Apart from its non-conformity with
standards, there are multiple other problems with its code quality and the way
it is maintained. Consider using e.g. :doc:`xandikos` instead.

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
