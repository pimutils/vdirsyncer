* If you're reporting an issue with vdirsyncer:

  * Make sure you have the latest version by executing ``pip install --user
    --upgrade vdirsyncer``.

  * Include the Python version, your configuration, the commands you're
    executing, and their output.

  * Use ``--verbosity=DEBUG`` when including output from vdirsyncer.

* If you're suggesting a feature, keep in mind that vdirsyncer tries not to be
  a full calendar or contacts client, but rather just the piece of software
  that synchronizes all the data. If you're looking for a viewer for the
  calendar data you've synced, `khal <https://github.com/geier/khal>`_ is what
  you're looking for.

* If you're submitting pull requests:

  * Make sure your tests pass on Travis.

  * But not because you wrote too few tests.

  * Add yourself to ``CONTRIBUTORS.rst``. Don't add anything to
    ``CHANGELOG.rst``, I do that myself shortly before the release. You can
    help by writing meaningful commit messages.
