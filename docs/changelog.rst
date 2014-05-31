=========
Changelog
=========

This changelog only contains information that might be useful to end users and
package maintainers. For further info, see the git commit log.

Version 0.1.6
=============

*unreleased*

- vdirsyncer now depends on the ``icalendar`` package from PyPI, to get rid of
  its own broken parser.

- vdirsyncer now also depends on ``requests_toolbelt``. This makes it possible
  to guess the authentication type instead of blankly assuming ``basic``.

- Fix a semi-bug in caldav and carddav storages where a tuple (href, etag)
  instead of the proper etag would have been returned from the upload method.
  vdirsyncer might do unnecessary copying when upgrading to this version.

- Add the storage :py:class:`vdirsyncer.storage.SingleFileStorage`. See issue
  `#48`_.

- The ``collections`` parameter for pair sections now accepts the special
  values ``from a`` and ``from b`` for automatically discovering collections.
  See :ref:`pair_config`.

.. _`#48`: https://github.com/untitaker/vdirsyncer/issues/48

Version 0.1.5
=============

*released on 14 May 2014*

- Introduced changelogs

- Many bugfixes

- Many doc fixes

- vdirsyncer now doesn't necessarily need UIDs anymore for synchronization.

- vdirsyncer now aborts if one collection got completely emptied between
  synchronizations. See `#42`_.

.. _`#42`: https://github.com/untitaker/vdirsyncer/issues/42
