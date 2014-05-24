#!/bin/sh
set -e
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

install_build_tests() {
    $PIP_INSTALL \
        coverage \
        pytest \
        pytest-xprocess \
        git+https://github.com/geier/leif
    _davserver $DAV_SERVER
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
