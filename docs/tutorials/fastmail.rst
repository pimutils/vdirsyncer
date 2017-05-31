========
FastMail
========

Vdirsyncer is continuously tested against FastMail_, thanks to them for
providing a free account for this purpose. There are no known issues with it.
`FastMail's support pages
<https://www.fastmail.com/help/technical/servernamesandports.html>`_ provide
the settings to use::

    [storage cal]
    type = "caldav"
    url = "https://caldav.messagingengine.com/"
    username = ...
    password = ...

    [storage card]
    type = "carddav"
    url = "https://carddav.messagingengine.com/"
    username = ...
    password = ...

.. _FastMail: https://www.fastmail.com/
