========
FastMail
========

Vdirsyncer is irregularly tested against FastMail_. There are no known issues
with it. `FastMail's support pages
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
