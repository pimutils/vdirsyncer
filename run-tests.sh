#!/bin/sh
[[ -z "$DAV_SERVER" ]] && DAV_SERVER=radicale
[[ -z "$RADICALE_STORAGE" ]] && RADICALE_STORAGE=filesystem

davserver_radicale() { true; }
davserver_radicale_git() { true; }

davserver_owncloud() {
    sh ./owncloud-testserver/php.sh
}


# while it would be nice if the server was cleanly shut down, it's not really a
# problem either
davserver_$DAV_SERVER &
py.test $@
