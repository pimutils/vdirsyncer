=========
Changelog
=========

This changelog only contains information that might be useful to end users and
package maintainers. For further info, see the git commit log.

Version 0.2.5
=============

*released on 27 August 2014*

- Don't ask for the password of one server more than once and fix multiple
  concurrency issues, see issue `#101`_.

- Better validation of DAV endpoints.

.. _`#101`: https://github.com/untitaker/vdirsyncer/issues/101

Version 0.2.4
=============

*released on 18 August 2014*

- Include workaround for collection discovery with latest version of Radicale.

- Include metadata files such as the changelog or license in source
  distribution, see issues `#97`_ and `#98`_.

.. _`#97`: https://github.com/untitaker/vdirsyncer/issues/97
.. _`#98`: https://github.com/untitaker/vdirsyncer/issues/98

Version 0.2.3
=============

*released on 11 August 2014*

- Vdirsyncer now has a ``--version`` flag, see issue `#92`_.

- Fix a lot of bugs related to special characters in URLs, see issue `#49`_.

.. _`#92`: https://github.com/untitaker/vdirsyncer/issues/92
.. _`#49`: https://github.com/untitaker/vdirsyncer/issues/49

Version 0.2.2
=============

*released on 04 August 2014*

- Remove a security check that caused problems with special characters in DAV
  URLs and certain servers. On top of that, the security check was nonsensical.
  See issues `#87`_ and `#91`_.

- Change some errors to warnings, see issue `#88`_.

- Improve collection autodiscovery for servers without full support.

.. _`#87`: https://github.com/untitaker/vdirsyncer/issues/87
.. _`#88`: https://github.com/untitaker/vdirsyncer/issues/88
.. _`#91`: https://github.com/untitaker/vdirsyncer/issues/91

Version 0.2.1
=============

*released on 05 July 2014*

- Fix bug where vdirsyncer shows empty addressbooks when using CardDAV with
  Zimbra.

- Fix infinite loop when password doesn't exist in system keyring.

- Colorized errors, warnings and debug messages.

- vdirsyncer now depends on the ``click`` package instead of argvard.

Version 0.2.0
=============

*released on 12 June 2014*

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

- The ``read_only`` parameter was added to storage sections. See
  :ref:`storage_config`.

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
