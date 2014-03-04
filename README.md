***This is still work-in-progress! Expect breakage, bad docs and data-loss.***

[![Build Status](https://travis-ci.org/untitaker/vdirsyncer.png?branch=master)](https://travis-ci.org/untitaker/vdirsyncer)

vdirsyncer synchronizes your CalDAV calendars and CardDAV addressbooks between
two storages. The supported storages are CalDAV, CardDAV and
[vdir](https://github.com/untitaker/vdir).

It aims to be for CalDAV and CardDAV what
[OfflineIMAP](http://offlineimap.org/) is for IMAP.

## How to use

Copy `config.example` to `~/.vdirsyncer/config` and edit it. You can use the
`VDIRSYNCER_CONFIG` environment variable to change the path vdirsyncer will
read the config from.

Run `vdirsyncer --help`.

## How to run the tests

    pip install .
    sh install_deps.sh
    py.test
