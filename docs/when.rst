==========================
When do I need Vdirsyncer?
==========================

Why vdir?
=========

:doc:`vdir` is a compromise to maintain some compatibility with the CalDAV and
CardDAV protocols, which are supported by :ref:`ownCloud <owncloud_setup>`,
:ref:`Exchange <davmail_setup>`, :ref:`iCloud <icloud_setup>` and many other
services.

If you don't care about that, you don't need vdirsyncer. However, consider the
following before writing everything into a single text file:

Why not a simple text file? (todo.txt)
--------------------------------------

Projects like `todo.txt <http://todotxt.com/>`_ criticize the complexity of
modern productivity apps, and that rightfully. However, when they're faced with
the question how to synchronize that data across multiple devices, they seemed
to have reached the dead end with their novel idea: "Let's just use Dropbox".

What does file sync software do if both files have changed since the last sync?
The answer is to ignore the question, just sync as often as possible, and hope
for the best. Because if it comes to a sync conflict, most sync services are
not daring to merge files, and create two copies on each computer instead.
Merging the two task lists is left to the user.

A better idea would've been to use ``git`` to synchronize the ``todo.txt``
file, which is at least able to resolve some basic conflicts.

Why vdirsyncer?
===============

Why not Dropbox?
----------------

Since :doc:`vdirs <vdir>` are just a bunch of files, it is obvious to try
*file synchronization* for synchronizing your data between multiple computers,
such as:

* `Syncthing <https://syncthing.net/>`_
* `Dropbox <https://dropbox.com/>`_ or one of the gajillion services like it
* `unison <https://www.cis.upenn.edu/~bcpierce/unison/>`_

If you only need to synchronize things between several desktop machines (and
not e.g. smartphones), using any of those to sync your vdirs will probably fit
your usecase.

Since each contact/task/event is contained in its own file, the
chance of sync conflicts is relatively small, but those still happen.
Vdirsyncer doesn't do anything smart if two items have conflicting changes
either, but it could in the future.

Why not git?
------------

If file synchronization software and vdirsyncer are so dumb about sync
conflicts, why not use git then? Why not put your vdirs into a repo, and just
``git commit``, ``git push`` and ``git pull``? It has **many advantages over
both Vdirsyncer and Dropbox**:

* **Full change history:** If some stupid software deletes all your data, just
  revert the commit!

* **Better at merging in-file conflicts (sometimes):** If you changed the
  summary of a task on one computer and the due date on another one, git might
  be able to merge these two files to have the new summary *and* the new due
  date.
  
  Vdirsyncer is currently relatively stupid about this (see
  :ref:`conflict_resolution`), but in practice, I didn't find its stupidity to
  be problematic.

* **Superior server options:** ``sshd`` is vastly easier to set up and faster
  than any DAV-server I've ever seen. Passwordless authentication is also a
  huge win, although there are DAV-servers which provide that too.

* `Something about data integrity
  <https://stackoverflow.com/questions/27440322/data-integrity-in-git>`_.
  You'll quickly notice if your hardware is loosing your files, because git
  creates checksums of everything.

Many other CLI programs that need to sync data are based on git, for example
pass_ or ppl_. Those usually hide git behind a convenient CLI interface that at
least autocommits.

.. _pass: http://passwordstore.org/
.. _ppl: http://ppladdressbook.org/
