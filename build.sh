#!/bin/sh
set -e

[ -n "$DAV_SERVER" ] || DAV_SERVER=radicale
[ -n "$REQUIREMENTS" ] || REQUIREMENTS=release
[ -n "$PIP_INSTALL" ] || PIP_INSTALL="pip install"
[ -n "$TESTSERVER_BASE" ] || TESTSERVER_BASE=./tests/storage/dav/servers/


_optimize_pip() {
    # Optimize pip for packages with many C extensions. Comes with its own
    # cost, e.g. not worth it when running a style checker.

    if [ "$TRAVIS" = "true" ]; then
        export CFLAGS=-O0  # speed up builds of packages which don't have wheels
        $PIP_INSTALL --upgrade pip
        $PIP_INSTALL wheel
        PIP_INSTALL="pip install --use-wheel --find-links=http://travis-wheels.unterwaditzer.net/wheels/"
    fi
}


_davserver() {
    # Maybe tmpfs is mounted on /tmp/, can't harm anyway.
    if [ ! -d $TESTSERVER_BASE$1/ ]; then
        git clone --depth=1 \
            https://github.com/vdirsyncer/$1-testserver.git \
            /tmp/$1-testserver
        ln -s /tmp/$1-testserver $TESTSERVER_BASE$1
    fi
    (cd $TESTSERVER_BASE$1 && sh install.sh)
}

command__install_tests() {
    $PIP_INSTALL pytest pytest-xprocess pytest-localserver
    _optimize_pip
    _davserver $DAV_SERVER
    [ "$TRAVIS" != "true" ] || $PIP_INSTALL coverage coveralls
    $PIP_INSTALL --editable .
}

command__tests() {
    if [ "$TRAVIS" = "true" ]; then
        coverage run --source=vdirsyncer/ --module pytest
        coveralls
    else
        py.test
    fi
}


COMMAND="$1"
if [ -z "$COMMAND" ]; then
    echo "Usage: build.sh command"
    exit 1
fi

command__${COMMAND}
