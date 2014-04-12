#!/bin/sh
echo "The shell is $SHELL"
set -e
[ -n "$DAV_SERVER" ] || DAV_SERVER=radicale_filesystem
[ -n "$REQUIREMENTS" ] || REQUIREMENTS=release
TESTSERVER_BASE=./tests/storage/dav/servers/

PIP_INSTALL="pip install"
if [ "$IS_TRAVIS" = "true" ]; then
    export CFLAGS=-O0  # speed up builds of packages which don't have wheels
    PIP_INSTALL="pip install --use-wheel --find-links=http://dev.unterwaditzer.net/vdirsyncer/wheels/"
    pip install --upgrade wheel pip setuptools
fi

$PIP_INSTALL --editable .
$PIP_INSTALL -r requirements.txt


testserver_from_repo() {
    # Maybe tmpfs is mounted on /tmp/, can't harm anyway.
    if [ ! -d $TESTSERVER_BASE$1/ ]; then
        git clone --depth=1 \
            https://github.com/untitaker/$1-testserver.git \
            /tmp/$1-testserver
        mkdir testservers
        ln -s /tmp/$1-testserver $TESTSERVER_BASE$1
    fi
    cd $TESTSERVER_BASE$1
    sh install.sh
}

davserver_owncloud() {
    testserver_from_repo owncloud
}

davserver_radicale() {
    testserver_from_repo radicale
}



davserver_$DAV_SERVER
