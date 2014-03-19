#!/bin/sh
set -e
[ -n "$DAV_SERVER" ] || DAV_SERVER=radicale_filesystem

davserver_radicale_database() { true; }
davserver_radicale_filesystem() { true; }

davserver_owncloud() {
    sh ./owncloud-testserver/php.sh > /dev/null
}


# while it would be nice if the server was cleanly shut down, it's not really a
# problem either
davserver_$DAV_SERVER &
py.test $@
