.. _systemd_timer-tutorial:

Running as a systemd.timer
==========================

vdirsyncer includes unit files to run at an interval (by default every 15±5
minutes).

.. note::

    These are not installed when installing via pip, only via distribution
    packages. If you installed via pip, or your distribution doesn't ship systemd
    unit files, you'll need to download vdirsyncer.service_ and vdirsyncer.timer_
    into either ``/etc/systemd/user/`` or ``~/.local/share/systemd/user``.

.. _vdirsyncer.service: https://raw.githubusercontent.com/pimutils/vdirsyncer/master/contrib/vdirsyncer.service
.. _vdirsyncer.timer: https://raw.githubusercontent.com/pimutils/vdirsyncer/master/contrib/vdirsyncer.timer

Activation
----------

To activate the timer, just run ``systemctl --user enable vdirsyncer.timer``.
To see logs of previous runs, use ``journalctl --user -u vdirsyncer``.

Configuration
-------------

It's quite possible that the default "every fifteen minutes" interval isn't to
your liking. No default will suit everybody, but this is configurable by simply
running::

    systemctl --user edit vdirsyncer

This will open a blank editor, where you can override the timer by including::

    OnBootSec=5m  # This is how long after boot the first run takes place.
    OnUnitActiveSec=15m  # This is how often subsequent runs take place.
