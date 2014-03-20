#!/bin/sh
set -e
[ -n "$DAV_SERVER" ] || DAV_SERVER=radicale_filesystem
exec py.test $@
