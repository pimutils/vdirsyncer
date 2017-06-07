===============
Other tutorials
===============

The following section contains tutorials not explicitly about any particular
core function of vdirsyncer. They usually show how to integrate vdirsyncer with
third-party software. Because of that, it may be that the information regarding
that other software only applies to specific versions of them.

.. note::
    Please :doc:`contribute </contributing>` your own tutorials too!  Pages are
    often only stubs and are lacking full examples.

Ćlient applications
===================

.. toctree::
    :maxdepth: 1

    claws-mail
    systemd-timer
    todoman

Further applications, with missing pages:

- khal_, a CLI calendar application supporting :doc:`vdir </vdir>`. You can use
  :storage:`filesystem` with it.
- Many graphical calendar apps such as dayplanner_, Orage_ or rainlendar_ save
  a calendar in a single ``.ics`` file. You can use :storage:`singlefile` with
  those.
- khard_, a commandline addressbook supporting :doc:`vdir </vdir>`.  You can use
  :storage:`filesystem` with it.
- contactquery.c_, a small program explicitly written for querying vdirs from
  mutt.
- mates_, a commandline addressbook supporting :doc:`vdir </vdir>`.
- vdirel_, access :doc:`vdir </vdir>` contacts from Emacs.

.. _khal: http://lostpackets.de/khal/
.. _dayplanner: http://www.day-planner.org/
.. _Orage: http://www.kolumbus.fi/~w408237/orage/
.. _rainlendar: http://www.rainlendar.net/
.. _khard: https://github.com/scheibler/khard/
.. _contactquery.c: https://github.com/t-8ch/snippets/blob/master/contactquery.c
.. _mates: https://github.com/pimutils/mates.rs
.. _vdirel: https://github.com/DamienCassou/vdirel

.. _supported-servers:

Servers
=======

.. toctree::
    :maxdepth: 1

    baikal
    davmail
    fastmail
    google
    icloud
    nextcloud
    owncloud
    radicale
    xandikos
