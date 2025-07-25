=========
Changelog
=========

This changelog only contains information that might be useful to end users and
package maintainers. For further info, see the git commit log.

Package maintainers and users who have to manually update their installation
may want to subscribe to `GitHub's tag feed
<https://github.com/pimutils/vdirsyncer/tags.atom>`_.

Version 0.20.0
==============

- Remove dependency on abandoned ``atomicwrites`` library.
- Implement ``filter_hook`` for the HTTP storage.
- Drop support for Python 3.7.
- Add support for Python 3.12 and Python 3.13.

Version 0.19.3
==============

- Added a no_delete option to the storage configuration. :gh:`1090`
- Fix crash when running ``vdirsyncer repair`` on a collection. :gh:`1019`
- Add an option to request vCard v4.0.  :gh:`1066`
- Require matching ``BEGIN`` and ``END`` lines in vobjects. :gh:`1103`
- A Docker environment for Vdirsyncer has been added `Vdirsyncer DOCKERIZED <https://github.com/Bleala/Vdirsyncer-DOCKERIZED>`_.
- Implement digest auth. :gh:`1137`
- Add ``filter_hook`` parameter to :storage:`http`. :gh:`1136`

Version 0.19.2
==============

- Improve the performance of ``SingleFileStorage``. :gh:`818`
- Properly document some caveats of the Google Contacts storage.
- Fix crash when using auth certs. :gh:`1033`
- The ``filesystem`` storage can be specified with ``type =
  "filesystem/icalendar"`` or ``type = "filesystem/vcard"``. This has not
  functional impact, and is merely for forward compatibility with the Rust
  implementation of vdirsyncer.
- Python 3.10 and 3.11 are officially supported.
- Instructions for integrating with Google CalDav/CardDav have changed.
  Applications now need to be registered as "Desktop applications". Using "Web
  application" no longer works due to changes on Google's side. :gh:`1078`

Version 0.19.1
==============

- Fixed crash when operating on Google Contacts. :gh:`994`
- The ``HTTP_PROXY`` and ``HTTPS_PROXY`` are now respected. :gh:`1031`
- Instructions for integrating with Google CalDav/CardDav have changed.
  Applications now need to be registered as "Web Application". :gh:`975`
- Various documentation updates.

Version 0.19.0
==============

- Add "shell" password fetch strategy to pass command string to a shell.
- Add "description" and "order" as metadata.  These fetch the CalDAV:
  calendar-description, ``CardDAV:addressbook-description`` and
  ``apple-ns:calendar-order`` properties respectively.
- Add a new ``showconfig`` status. This prints *some* configuration values as
  JSON. This is intended to be used by external tools and helpers that interact
  with ``vdirsyncer``, and considered experimental.
- Update TLS-related tests that were failing due to weak MDs. :gh:`903`
- ``pytest-httpserver`` and ``trustme`` are now required for tests.
- ``pytest-localserver`` is no longer required for tests.
- Multithreaded support has been dropped. The ``"--max-workers`` has been removed.
- A new ``asyncio`` backend is now used. So far, this shows substantial speed
  improvements in ``discovery`` and ``metasync``, but little change in `sync`.
  This will likely continue improving over time. :gh:`906`
- The ``google`` storage types no longer require ``requests-oauthlib``, but
  require ``python-aiohttp-oauthlib`` instead.
- Vdirsyncer no longer includes experimental support for `EteSync
  <https://www.etesync.com/>`_. The existing integration had not been supported
  for a long time and no longer worked. Support for external storages may be
  added if anyone is interested in maintaining an EteSync plugin. EteSync
  users should consider using `etesync-dav`_.
- The ``plist`` for macOS has been dropped. It was broken and homebrew
  generates their own based on package metadata. macOS users are encouraged to
  use that as a reference.

.. _etesync-dav: https://github.com/etesync/etesync-dav

Changes to SSL configuration
----------------------------

Support for ``md5`` and ``sha1`` certificate fingerprints has been dropped. If
you're validating certificate fingerprints, use ``sha256`` instead.

When using a custom ``verify_fingerprint``, CA validation is always disabled.

If ``verify_fingerprint`` is unset, CA verification is always active. Disabling
both features is insecure and no longer supported.

The ``verify`` parameter no longer takes boolean values, it is now optional and
only takes a string to a custom CA for verification.

The ``verify`` and ``verify_fingerprint`` will likely be merged into a single
parameter in future.

Version 0.18.0
==============

Note: Version 0.17 has some alpha releases but ultimately was never finalised.
0.18 actually continues where 0.16 left off.

- Support for Python 3.5 and 3.6 has been dropped. This release mostly focuses
  on keeping vdirsyncer compatible with newer environments.
- click 8 and click-threading 0.5.0 are now required.
- For those using ``pipsi``, we now recommend using ``pipx``, it's successor.
- Python 3.9 is now supported.
- Our Debian/Ubuntu build scripts have been updated. New versions should be
  pushed to those repositories soon.

Version 0.16.8
==============

*released 09 June 2020*

- Support Python 3.7 and 3.8.

This release is functionally identical to 0.16.7.
It's been tested with recent Python versions, and has been marked as supporting
them. It will also be the final release supporting Python 3.5 and 3.6.

Version 0.16.7
==============

*released on 19 July 2018*

- Fixes for Python 3.7

Version 0.16.6
==============

*released on 13 June 2018*

- **Packagers:** Documentation building no longer needs a working installation
  of vdirsyncer.

Version 0.16.5
==============

*released on 13 June 2018*

- **Packagers:** click-log 0.3 is required.
- All output will now happen on stderr (because of the upgrade of ``click-log``).

Version 0.16.4
==============

*released on 05 February 2018*

- Fix tests for new Hypothesis version. (Literally no other change included)

Version 0.16.3
==============

*released on 03 October 2017*

- First version with custom Debian and Ubuntu packages. See :gh:`663`.
- Remove invalid ASCII control characters from server responses. See :gh:`626`.
- **packagers:** Python 3.3 is no longer supported. See :ghpr:`674`.

Version 0.16.2
==============

*released on 24 August 2017*

- Fix crash when using daterange or item_type filters in
  :storage:`google_calendar`, see :gh:`657`.
- **Packagers:** Fixes for new version ``0.2.0`` of ``click-log``. The version
  requirements for the dependency ``click-log`` changed.

Version 0.16.1
==============

*released on 8 August 2017*

- Removed remoteStorage support, see :gh:`647`.
- Fixed test failures caused by latest requests version, see :gh:`660`.

Version 0.16.0
==============

*released on 2 June 2017*

- Strip ``METHOD:PUBLISH`` added by some calendar providers, see :gh:`502`.
- Fix crash of Google storages when saving token file.
- Make DAV discovery more RFC-conformant, see :ghpr:`585`.
- Vdirsyncer is now tested against Xandikos, see :ghpr:`601`.
- Subfolders with a leading dot are now ignored during discover for
  ``filesystem`` storage. This makes it easier to combine it with version
  control.
- Statuses are now stored in a sqlite database. Old data is automatically
  migrated. Users with really large datasets should encounter performance
  improvements. This means that **sqlite3 is now a dependency of vdirsyncer**.
- **Vdirsyncer is now licensed under the 3-clause BSD license**, see :gh:`610`.
- Vdirsyncer now includes experimental support for `EteSync
  <https://www.etesync.com/>`_, see :ghpr:`614`.
- Vdirsyncer now uses more filesystem metadata for determining whether an item
  changed. You will notice a **possibly heavy CPU/IO spike on the first sync
  after upgrading**.
- **Packagers:** Reference ``systemd.service`` and ``systemd.timer`` unit files
  are provided. It is recommended to install these as documentation if your
  distribution is systemd-based.

Version 0.15.0
==============

*released on 28 February 2017*

- Deprecated syntax for configuration values is now completely rejected. All
  values now have to be valid JSON.
- A few UX improvements for Google storages, see :gh:`549` and :gh:`552`.
- Fix collection discovery for :storage:`google_contacts`, see :gh:`564`.
- iCloud is now tested on Travis, see :gh:`567`.

Version 0.14.1
==============

*released on 05 January 2017*

- ``vdirsyncer repair`` no longer changes "unsafe" UIDs by default, an extra
  option has to be specified. See :gh:`527`.
- A lot of important documentation updates.

Version 0.14.0
==============

*released on 26 October 2016*

- ``vdirsyncer sync`` now continues other uploads if one upload failed.  The
  exit code in such situations is still non-zero.
- Add ``partial_sync`` option to pair section. See :ref:`the config docs
  <partial_sync_def>`.
- Vdirsyncer will now warn if there's a string without quotes in your config.
  Please file issues if you find documentation that uses unquoted strings.
- Fix an issue that would break khal's config setup wizard.

Version 0.13.1
==============

*released on 30 September 2016*

- Fix a bug that would completely break collection discovery.

Version 0.13.0
==============

*released on 29 September 2016*

- Python 2 is no longer supported at all. See :gh:`219`.
- Config sections are now checked for duplicate names. This also means that you
  cannot have a storage section ``[storage foo]`` and a pair ``[pair foo]`` in
  your config, they have to have different names. This is done such that
  console output is always unambiguous. See :gh:`459`.
- Custom commands can now be used for conflict resolution during sync. See
  :gh:`127`.
- :storage:`http` now completely ignores UIDs. This avoids a lot of unnecessary
  down- and uploads.

Version 0.12.1
==============

*released on 20 August 2016*

- Fix a crash for Google and DAV storages. See :ghpr:`492`.
- Fix an URL-encoding problem with DavMail. See :gh:`491`.

Version 0.12
============

*released on 19 August 2016*

- :storage:`singlefile` now supports collections. See :ghpr:`488`.

Version 0.11.3
==============

*released on 29 July 2016*

- Default value of ``auth`` parameter was changed from ``guess`` to ``basic``
  to resolve issues with the Apple Calendar Server (:gh:`457`) and improve
  performance. See :gh:`461`.
- **Packagers:** The ``click-threading`` requirement is now ``>=0.2``. It was
  incorrect before. See :gh:`478`.
- Fix a bug in the DAV XML parsing code that would make vdirsyncer crash on
  certain input. See :gh:`480`.
- Redirect chains should now be properly handled when resolving ``well-known``
  URLs. See :ghpr:`481`.

Version 0.11.2
==============

*released on 15 June 2016*

- Fix typo that would break tests.

Version 0.11.1
==============

*released on 15 June 2016*

- Fix a bug in collection validation.
- Fix a cosmetic bug in debug output.
- Various documentation improvements.

Version 0.11.0
==============

*released on 19 May 2016*

- Discovery is no longer automatically done when running ``vdirsyncer sync``.
  ``vdirsyncer discover`` now has to be explicitly called.
- Add a ``.plist`` example for Mac OS X.
- Usage under Python 2 now requires a special config parameter to be set.
- Various deprecated configuration parameters do no longer have specialized
  errormessages. The generic error message for unknown parameters is shown.

  - Vdirsyncer no longer warns that the ``passwordeval`` parameter has been
    renamed to ``password_command``.

  - The ``keyring`` fetching strategy has been dropped some versions ago, but
    the specialized error message has been dropped.

  - An old status format from version 0.4 is no longer supported. If you're
    experiencing problems, just delete your status folder.

Version 0.10.0
==============

*released on 23 April 2016*

- New storage types :storage:`google_calendar` and :storage:`google_contacts`
  have been added.
- New global command line option `--config`, to specify an alternative config
  file. See :gh:`409`.
- The ``collections`` parameter can now be used to synchronize
  differently-named collections with each other.
- **Packagers:** The ``lxml`` dependency has been dropped.
- XML parsing is now a lot stricter. Malfunctioning servers that used to work
  with vdirsyncer may stop working.

Version 0.9.3
=============

*released on 22 March 2016*

- :storage:`singlefile` and :storage:`http` now handle recurring events
  properly.
- Fix a typo in the packaging guidelines.
- Moved to ``pimutils`` organization on GitHub. Old links *should* redirect,
  but be aware of client software that doesn't properly handle redirects.

Version 0.9.2
=============

*released on 13 March 2016*

- Fixed testsuite for environments that don't have any web browser installed.
  See :ghpr:`384`.

Version 0.9.1
=============

*released on 13 March 2016*

- Removed leftover debug print statement in ``vdirsyncer discover``, see commit
  ``3d856749f37639821b148238ef35f1acba82db36``.

- ``metasync`` will now strip whitespace from the start and the end of the
  values. See :gh:`358`.

- New ``Packaging Guidelines`` have been added to the documentation.

Version 0.9.0
=============

*released on 15 February 2016*

- The ``collections`` parameter is now required in pair configurations.
  Vdirsyncer will tell you what to do in its error message. See :gh:`328`.

Version 0.8.1
=============

*released on 30 January 2016*

- Fix error messages when invalid parameter fetching strategy is used. This is
  important because users would receive awkward errors for using deprecated
  ``keyring`` fetching.

Version 0.8.0
=============

*released on 27 January 2016*

- Keyring support has been removed, which means that ``password.fetch =
  ["keyring", "example.com", "myuser"]`` doesn't work anymore.

  For existing setups: Use ``password.fetch = ["command", "keyring", "get",
  "example.com", "myuser"]`` instead, which is more generic. See the
  documentation for details.

- Now emitting a warning when running under Python 2. See :gh:`219`.

Version 0.7.5
=============

*released on 23 December 2015*

- Fixed a bug in :storage:`remotestorage` that would try to open a CLI browser
  for OAuth.
- Fix a packaging bug that would prevent vdirsyncer from working with newer
  lxml versions.

Version 0.7.4
=============

*released on 22 December 2015*

- Improved error messages instead of faulty server behavior, see :gh:`290` and
  :gh:`300`.
- Safer shutdown of threadpool, avoid exceptions, see :gh:`291`.
- Fix a sync bug for read-only storages see commit
  ``ed22764921b2e5bf6a934cf14aa9c5fede804d8e``.
- Etag changes are no longer sufficient to trigger sync operations. An actual
  content change is also necessary. See :gh:`257`.
- :storage:`remotestorage` now automatically opens authentication dialogs in
  your configured GUI browser.
- **Packagers:** ``lxml>=3.1`` is now required (newer lower-bound version).

Version 0.7.3
=============

*released on 05 November 2015*

- Make remotestorage-dependencies actually optional.

Version 0.7.2
=============

*released on 05 November 2015*

- Un-break testsuite.

Version 0.7.1
=============

*released on 05 November 2015*

- **Packagers:** The setuptools extras ``keyring`` and ``remotestorage`` have
  been added. They're basically optional dependencies. See ``setup.py`` for
  more details.

- Highly experimental remoteStorage support has been added. It may be
  completely overhauled or even removed in any version.

- Removed mentions of old ``password_command`` in documentation.

Version 0.7.0
=============

*released on 27 October 2015*

- **Packagers:** New dependencies are ``click_threading``, ``click_log`` and
  ``click>=5.0``.
- ``password_command`` is gone. Keyring support got completely overhauled. See
  :doc:`keyring`.

Version 0.6.0
=============

*released on 06 August 2015*

- ``password_command`` invocations with non-zero exit code are now fatal (and
  will abort synchronization) instead of just producing a warning.
- Vdirsyncer is now able to synchronize metadata of collections. Set ``metadata
  = ["displayname"]`` and run ``vdirsyncer metasync``.
- **Packagers:** Don't use the GitHub tarballs, but the PyPI ones.
- **Packagers:** ``build.sh`` is gone, and ``Makefile`` is included in
  tarballs. See the content of ``Makefile`` on how to run tests post-packaging.
- ``verify_fingerprint`` doesn't automatically disable ``verify`` anymore.

Version 0.5.2
=============

*released on 15 June 2015*

- Vdirsyncer now checks and corrects the permissions of status files.
- Vdirsyncer is now more robust towards changing UIDs inside items.
- Vdirsyncer is now handling unicode hrefs and UIDs correctly. Software that
  produces non-ASCII UIDs is broken, but apparently it exists.

Version 0.5.1
=============

*released on 29 May 2015*

- **N.b.: The PyPI upload of 0.5.0 is completely broken.**
- Raise version of required requests-toolbelt to ``0.4.0``.
- Command line should be a lot faster when no work is done, e.g. for help
  output.
- Fix compatibility with iCloud again.
- Use only one worker if debug mode is activated.
- ``verify=false`` is now disallowed in vdirsyncer, please use
  ``verify_fingerprint`` instead.
- Fixed a bug where vdirsyncer's DAV storage was not using the configured
  useragent for collection discovery.

Version 0.4.4
=============

*released on 12 March 2015*

- Support for client certificates via the new ``auth_cert``
  parameter, see :gh:`182` and :ghpr:`183`.
- The ``icalendar`` package is no longer required.
- Several bugfixes related to collection creation.

Version 0.4.3
=============

*released on 20 February 2015*

- More performance improvements to ``singlefile``-storage.
- Add ``post_hook`` param to ``filesystem``-storage.
- Collection creation now also works with SabreDAV-based servers, such as
  Baikal or ownCloud.
- Removed some workarounds for Radicale. Upgrading to the latest Radicale will
  fix the issues.
- Fixed issues with iCloud discovery.
- Vdirsyncer now includes a simple ``repair`` command that seeks to fix some
  broken items.

Version 0.4.2
=============

*released on 30 January 2015*

- Vdirsyncer now respects redirects when uploading and updating items. This
  might fix issues with Zimbra.
- Relative ``status_path`` values are now interpreted as relative to the
  configuration file's directory.
- Fixed compatibility with custom SabreDAV servers. See :gh:`166`.
- Catch harmless threading exceptions that occur when shutting down vdirsyncer.
  See :gh:`167`.
- Vdirsyncer now depends on ``atomicwrites``.
- Massive performance improvements to ``singlefile``-storage.
- Items with extremely long UIDs should now be saved properly in
  ``filesystem``-storage. See :gh:`173`.

Version 0.4.1
=============

*released on 05 January 2015*

- All ``create`` arguments from all storages are gone. Vdirsyncer now asks if
  it should try to create collections.
- The old config values ``True``, ``False``, ``on``, ``off`` and ``None`` are
  now invalid.
- UID conflicts are now properly handled instead of ignoring one item. Card-
  and CalDAV servers are already supposed to take care of those though.
- Official Baikal support added.

Version 0.4.0
=============

*released on 31 December 2014*

- The ``passwordeval`` parameter has been renamed to ``password_command``.
- The old way of writing certain config values such as lists is now gone.
- Collection discovery has been rewritten. Old configuration files should be
  compatible with it, but vdirsyncer now caches the results of the collection
  discovery. You have to run ``vdirsyncer discover`` if collections were added
  or removed on one side.
- Pair and storage names are now restricted to certain characters. Vdirsyncer
  will issue a clear error message if your configuration file is invalid in
  that regard.
- Vdirsyncer now supports the XDG-Basedir specification. If the
  ``VDIRSYNCER_CONFIG`` environment variable isn't set and the
  ``~/.vdirsyncer/config`` file doesn't exist, it will look for the
  configuration file at ``$XDG_CONFIG_HOME/vdirsyncer/config``.
- Some improvements to CardDAV and CalDAV discovery, based on problems found
  with FastMail. Support for ``.well-known``-URIs has been added.

Version 0.3.4
=============

*released on 8 December 2014*

- Some more bugfixes to config handling.

Version 0.3.3
=============

*released on 8 December 2014*

- Vdirsyncer now also works with iCloud. Particularly collection discovery and
  etag handling were fixed.
- Vdirsyncer now encodes Cal- and CardDAV requests differently. This hasn't
  been well-tested with servers like Zimbra or SoGo, but isn't expected to
  cause any problems.
- Vdirsyncer is now more robust regarding invalid responses from CalDAV
  servers. This should help with future compatibility with Davmail/Outlook.
- Fix a bug when specifying ``item_types`` of :storage:`caldav` in the
  deprecated config format.
- Fix a bug where vdirsyncer would ignore all but one character specified in
  ``unsafe_href_chars`` of :storage:`caldav` and :storage:`carddav`.

Version 0.3.2
=============

*released on 3 December 2014*

- The current config format has been deprecated, and support for it will be
  removed in version 0.4.0. Vdirsyncer warns about this now.

Version 0.3.1
=============

*released on 24 November 2014*

- Fixed a bug where vdirsyncer would delete items if they're deleted on side A
  but modified on side B. Instead vdirsyncer will now upload the new items to
  side A. See :gh:`128`.

- Synchronization continues with the remaining pairs if one pair crashes, see
  :gh:`121`.

- The ``processes`` config key is gone. There is now a ``--max-workers`` option
  on the CLI which has a similar purpose. See :ghpr:`126`.

- The Read The Docs-theme is no longer required for building the docs. If it is
  not installed, the default theme will be used. See :gh:`134`.

Version 0.3.0
=============

*released on 20 September 2014*

- Add ``verify_fingerprint`` parameter to :storage:`http`, :storage:`caldav`
  and :storage:`carddav`, see :gh:`99` and :ghpr:`106`.

- Add ``passwordeval`` parameter to :ref:`general_config`, see :gh:`108` and
  :ghpr:`117`.

- Emit warnings (instead of exceptions) about certain invalid responses from
  the server, see :gh:`113`.  This is apparently required for compatibility
  with Davmail.

Version 0.2.5
=============

*released on 27 August 2014*

- Don't ask for the password of one server more than once and fix multiple
  concurrency issues, see :gh:`101`.

- Better validation of DAV endpoints.

Version 0.2.4
=============

*released on 18 August 2014*

- Include workaround for collection discovery with latest version of Radicale.

- Include metadata files such as the changelog or license in source
  distribution, see :gh:`97` and :gh:`98`.

Version 0.2.3
=============

*released on 11 August 2014*

- Vdirsyncer now has a ``--version`` flag, see :gh:`92`.

- Fix a lot of bugs related to special characters in URLs, see :gh:`49`.

Version 0.2.2
=============

*released on 04 August 2014*

- Remove a security check that caused problems with special characters in DAV
  URLs and certain servers. On top of that, the security check was nonsensical.
  See :gh:`87` and :gh:`91`.

- Change some errors to warnings, see :gh:`88`.

- Improve collection autodiscovery for servers without full support.

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

- Add the storage :storage:`singlefile`. See :gh:`48`.

- The ``collections`` parameter for pair sections now accepts the special
  values ``from a`` and ``from b`` for automatically discovering collections.
  See :ref:`pair_config`.

- The ``read_only`` parameter was added to storage sections. See
  :ref:`storage_config`.

Version 0.1.5
=============

*released on 14 May 2014*

- Introduced changelogs

- Many bugfixes

- Many doc fixes

- vdirsyncer now doesn't necessarily need UIDs anymore for synchronization.

- vdirsyncer now aborts if one collection got completely emptied between
  synchronizations. See :gh:`42`.
