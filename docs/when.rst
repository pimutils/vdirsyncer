==========================
When do I need Vdirsyncer?
==========================

Why not Dropbox + todo.txt?
---------------------------

Projects like `todo.txt <http://todotxt.com/>`_ criticize the complexity of
modern productivity apps, and that rightfully. So they set out to create a new,
super-simple, human-readable format, such that vim suffices for viewing the raw
data. However, when they're faced with the question how to synchronize that
data across multiple devices, they seemed to have reached the dead end with
their novel idea: "Let's just use Dropbox".

What does file sync software do if both files have changed since the last sync?
The answer is to ignore the question, just sync as often as possible, and hope
for the best. Because if it comes to a sync conflict, most sync services are
not daring to merge files, and create two copies on each computer instead.
Merging the two task lists is left to the user.

A better idea would've been to use ``git`` to synchronize the ``todo.txt``
file, which is at least able to resolve some basic conflicts.

Why not file sync (Dropbox, git, ...) + vdir?
---------------------------------------------

Since :doc:`vdirs <vdir>` are just a bunch of files, it is obvious to try *file
synchronization* for synchronizing your data between multiple computers, such
as:

* `Syncthing <https://syncthing.net/>`_
* `Dropbox <https://dropbox.com/>`_ or one of the gajillion services like it
* `unison <https://www.cis.upenn.edu/~bcpierce/unison/>`_
* Just ``git`` with a ``sshd``.

The disadvantages of those solutions largely depend on the exact file sync
program chosen:

* Like with ``todo.txt``, Dropbox and friends are obviously agnostic/unaware of
  the files' contents. If a file has changed on both sides, Dropbox just copies
  both versions to both sides.
  
  This is a good idea if the user is directly interfacing with the file system
  and is able to resolve conflicts themselves.  Here it might lead to
  errorneous behavior with e.g. ``khal``, since there are now two events with
  the same UID.

  This point doesn't apply to git: It has very good merging capabilities,
  better than what vdirsyncer currently has.

* Such a setup doesn't work at all with smartphones. Vdirsyncer, on the other
  hand, synchronizes with CardDAV/CalDAV servers, which can be accessed with
  e.g. DAVDroid_ or the apps by dmfs_.

.. _DAVDroid: http://davdroid.bitfire.at/
.. _dmfs: https://dmfs.org/
