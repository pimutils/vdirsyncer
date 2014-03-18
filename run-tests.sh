#!/bin/sh
[[ -z "$DAV_SERVER" ]] && DAV_SERVER=radicale
[[ -z "$RADICALE_STORAGE" ]] && RADICALE_STORAGE=filesystem

davserver_radicale() { true; }
davserver_radicale_git() { true; }

davserver_owncloud() {
    sh ./owncloud-testserver/php.sh
}


davserver_$DAV_SERVER &
DAVSERVER_PID=$!
py.test ./tests/
kill -9 $DAVSERVER_PID
wait
