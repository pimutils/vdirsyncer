This is work-in-progress.

A basic syncronization utility for [vdir](https://github.com/untitaker/vdir).
Should be able to sync both CardDAV and CalDAV in the end.

## How to run

Copy `config.example` to `~/.vdirsyncer/config` and edit it. You can use the
`VDIRSYNCER_CONFIG` environment variable to change the path vdirsyncer will
read the config from.

Run `vdirsyncer --help`.

## A little bit about the code architecture

There are storage classes which control the access to one vdir-collection and
offer basic CRUD-ish methods for modifying those collections. The exact
interface is described in `vdirsyncer.storage.base`, the `Storage` class should
be a superclass of all storage classes.

One function in `vdirsyncer.sync` can then be called on two instances of
`Storage` to syncronize them, due to the abstract API storage classes are
implementing, the two given instances don't have to be of the same exact type.
This allows us not only to syncronize a local vdir with a CalDAV server, but
also syncronize two CalDAV servers or two local vdirs.
