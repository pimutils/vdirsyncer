=======================
The vdir Storage Format
=======================

This document describes a standard for storing calendars and contacts on a
filesystem, with the main goal of being easy to implement.

Basic Structure
===============

The main folder (root) contains an arbitrary number of subfolders
(collections), which contain only files (items). Synonyms for "collection" may
be "addressbook" or "calendar".

An item is:

- A vCard_ file, in which case the file extension *must* be `.vcf`, *or*
- An iCalendar_ file, in which case the file extension *must* be `.ics`.

An item *should* contain a ``UID`` property as described by the vCard and
iCalendar standards.

The filename *must* consist of the ``ident``, followed by the file extension.
The ``ident`` is either the ``UID``, if the item has one, else a string with
similar properties as the ``UID``:

   Type name: UID

   Type purpose: To specify a value that represents a globally unique
   identifier corresponding to the individual or resource associated
   with the vCard.

   -- The vCard_ RFC

One reason this format was chosen is due to its compatibility with the CardDAV_
and CalDAV_ standards.

.. _vCard: https://tools.ietf.org/html/rfc6350
.. _iCalendar: https://tools.ietf.org/html/rfc5545
.. _CardDAV: http://tools.ietf.org/html/rfc6352
.. _CalDAV: http://tools.ietf.org/search/rfc4791

Writing to vdirs
================

Creating and modifying items *should* happen atomically_.

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

Rationale
=========

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
