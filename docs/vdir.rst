=======================
The Vdir Storage Format
=======================

This document describes a standard for storing calendars and contacts on a
filesystem, with the main goal of being easy to implement.

Vdirsyncer synchronizes to vdirs via :storage:`filesystem`. Each vdir
(basically just a directory with some files in it) represents a calendar or
addressbook.

Basic Structure
===============

The main folder (root) contains an arbitrary number of subfolders
(collections), which contain only files (items). Synonyms for "collection" may
be "addressbook" or "calendar".

An item is:

- A vCard_ file, in which case the file extension *must* be `.vcf`, *or*
- An iCalendar_ file, in which case the file extension *must* be `.ics`.

An item *should* contain a ``UID`` property as described by the vCard and
iCalendar standards. If it contains more than one ``UID`` property, the values
of those *must* not differ.

The file *must* contain exactly one event, task or contact. In most cases this
also implies only one ``VEVENT``/``VTODO``/``VCARD`` component per file, but
e.g.  recurrence exceptions would require multiple ``VEVENT`` components per
event.

The filename *should* consist of the ``ident``, followed by the file extension.
The ``ident`` is either the ``UID``, if the item has one, else a string with
similar properties as the ``UID``. However, several restrictions of the
underlying filesystem might make an implementation of this naming scheme for
items' filenames impossible. The approach to deal with such cases is left to
the client, which are free to choose a different scheme for filenames instead.

.. _vCard: https://tools.ietf.org/html/rfc6350
.. _iCalendar: https://tools.ietf.org/html/rfc5545
.. _CardDAV: http://tools.ietf.org/html/rfc6352
.. _CalDAV: http://tools.ietf.org/search/rfc4791

Metadata
========

Any of the below metadata files may be absent. None of the files listed below
have any file extensions.

- A file called ``color`` inside the vdir indicates the vdir's color, a
  property that is only relevant in UI design.

  Its content is an ASCII-encoded hex-RGB value of the form ``#RRGGBB``. For
  example, a file content of ``#FF0000`` indicates that the vdir has a red
  (user-visible) color. No short forms or informal values such as ``red`` (as
  known from CSS, for example) are allowed. The prefixing ``#`` must be
  present.

- A file called ``displayname`` contains a UTF-8 encoded label that may be used
  to represent the vdir in UIs.

Writing to vdirs
================

Creating and modifying items or metadata files *should* happen atomically_.

Writing to a temporary file on the same physical device, and then moving it to
the appropriate location is usually a very effective solution. For this
purpose, files with the extension ``.tmp`` may be created inside collections.

When changing an item, the original filename *must* be used.

.. _atomically: https://en.wikipedia.org/wiki/Atomicity_%28programming%29

Reading from vdirs
==================

- Any file ending with the ``.tmp`` or no file extension *must not* be treated
  as an item.

- The ``ident`` part of the filename *should not* be parsed to improve the
  speed of item lookup.

Considerations
==============

The primary reason this format was chosen is due to its compatibility with the
CardDAV_ and CalDAV_ standards.

Performance
-----------

Currently, vdirs suffer from a rather major performance problem, one which
current implementations try to mitigate by building up indices of the
collections for faster search and lookup.

The reason items' filenames don't contain any extra information is simple: The
solutions presented induced duplication of data, where one duplicate might
become out of date because of bad implementations. As it stands right now, a
index format could be formalized separately though.

vdirsyncer doesn't really have to bother about efficient item lookup, because
its synchronization algorithm needs to fetch the whole list of items anyway.
Detecting changes is easily implemented by checking the files' modification
time.
