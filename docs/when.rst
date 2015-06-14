==========================
When do I need Vdirsyncer?
==========================

*TL;DR: Only if you want to sync with a smartphone.*

Why not Dropbox? (or anything like it)
======================================

Since :doc:`vdirs <vdir>` are just a bunch of files, it is obvious to try
*file synchronization* for synchronizing your data between multiple computers,
such as:

* `Syncthing <https://syncthing.net/>`_
* `Dropbox <https://dropbox.com/>`_ or one of the gajillion services like it
* `unison <https://www.cis.upenn.edu/~bcpierce/unison/>`_

If you only need to synchronize things between several desktop machines (and
not e.g. smartphones), using any of those to sync your vdirs will probably fit
your usecase.

**However**, be aware that none of those services are capable of solving
synchronization conflicts properly if you have all of your data in a single
file. Projects like `todo.txt <http://todotxt.com/>`_ get bitten by this
because they have all data in a single file: This means that if you change
*anything in your task list on two devices*, you have to merge those lists
manually. At least this is the case with Dropbox, which will create two
``todo.txt`` files in such situations.

Why not git?
============

If file synchronization software is so dumb about sync conflicts, why not use
git then? Why not put your vdirs into a repo, and just ``git commit``, ``git
push`` and ``git pull``? It has **many advantages over both Vdirsyncer and
Dropbox**:

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

Given that, **the only reason why you should choose vdirsyncer over git is its
compatibility with existing services**: Git can't sync with your :ref:`iCloud
<icloud_setup>`, :ref:`Exchange server <davmail_setup>` or :ref:`ownCloud
<owncloud_setup>`. And not with your smartphone.

You can also employ a mixture of vdirsyncer and git to enjoy the advantages of
both. This is the approach I am currently using.

.. _pass: http://passwordstore.org/
.. _ppl: http://ppladdressbook.org/
