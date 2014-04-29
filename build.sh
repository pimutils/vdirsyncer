#!/bin/sh
set -e
_testserver_from_repo() {
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

_install_testrunner() {
    $PIP_INSTALL pytest pytest-xprocess git+https://github.com/geier/leif
}

_davserver_owncloud() {
    _testserver_from_repo owncloud
}

_davserver_radicale() {
    _testserver_from_repo radicale
}


install_build_tests() {
    _install_testrunner
    _davserver_$DAV_SERVER
    if [ "$TRAVIS" = "true" ]; then
        export CFLAGS=-O0  # speed up builds of packages which don't have wheels
        $PIP_INSTALL --upgrade wheel pip setuptools
        PIP_INSTALL="pip install --use-wheel --find-links=http://dev.unterwaditzer.net/vdirsyncer/wheels/"
        $PIP_INSTALL coveralls
    fi

    $PIP_INSTALL --editable .
}

run_build_tests() {
    coverage run --source=vdirsyncer/,tests/ --module pytest
    if [ "$TRAVIS" = "true" ]; then
        coveralls
    fi
}

install_build_style() {
    $PIP_INSTALL flake8
}

run_build_style() {
    flake8 vdirsyncer tests
}


[ -n "$BUILD" ] || BUILD=tests
[ -n "$DAV_SERVER" ] || DAV_SERVER=radicale
[ -n "$REQUIREMENTS" ] || REQUIREMENTS=release
COMMAND="$1"
TESTSERVER_BASE=./tests/storage/dav/servers/

install_builds() {
    echo "Installing for $BUILD"
    PIP_INSTALL="pip install"
    install_build_$BUILD
}

run_builds() {
    echo "Running $BUILD"
    run_build_$BUILD
}

${COMMAND}_builds
