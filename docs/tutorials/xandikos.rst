========
Xandikos
========

Xandikos_ is a lightweight, yet complete CalDAV and CardDAV server, backed by
git. Vdirsyncer is continuously tested against its latest version.

After running ``./bin/xandikos --defaults -d $HOME/dav``, you should be able to
point vdirsyncer against the root of Xandikos like this::

    [storage cal]
    type = "caldav"
    url = "https://xandikos.example.com/"
    username = ...
    password = ...

    [storage card]
    type = "carddav"
    url = "https://xandikos.example.com/"
    username = ...
    password = ...

.. _Xandikos: https://github.com/jelmer/xandikos
