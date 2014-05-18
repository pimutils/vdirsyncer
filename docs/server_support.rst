==============
Server support
==============

vdirsyncer is currently tested against the latest versions of Radicale and
ownCloud.

Radicale
========

Radicale doesn't `support time ranges in the calendar-query of CalDAV/CardDAV
<https://github.com/Kozea/Radicale/issues/146>`_, so setting ``start_date`` and
``end_date`` in vdirsyncer's configuration will have no or unpredicted
consequences.

ownCloud
========

ownCloud uses SabreDAV, which had problems detecting collisions and
race-conditions. The problems were reported and are fixed in SabreDAV's repo.
See `Bug #16 <https://github.com/untitaker/vdirsyncer/issues/16>`_ for more
information.

However, given that this is a problem with every setup involving ownCloud, and
that ownCloud is widely used, it apparently isn't big enough of a problem yet.
