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
        pytest-xprocess
    _davserver $DAV_SERVER
    if [ "$TRAVIS" = "true" ]; then
        export CFLAGS=-O0  # speed up builds of packages which don't have wheels
        $PIP_INSTALL --upgrade pip
        $PIP_INSTALL wheel
        PIP_INSTALL="pip install --use-wheel --find-links=http://travis-wheels.unterwaditzer.net/wheels/"
        $PIP_INSTALL coveralls
    fi

    $PIP_INSTALL --editable .
}

run_build_tests() {
    if [ "$TRAVIS" = "true" ]; then
        coverage run --source=vdirsyncer/,tests/ --module pytest
        coveralls
    else
        py.test
    fi
}

install_build_style() {
    $PIP_INSTALL flake8
}

run_build_style() {
    flake8 vdirsyncer tests
    ! git grep -il syncroniz $(ls | grep -v 'build.sh')
}

install_build_docs() {
    $PIP_INSTALL sphinx sphinx_rtd_theme
    $PIP_INSTALL -e .
}

run_build_docs() {
    cd docs
    make html
}


[ -n "$BUILD" ] || BUILD=tests
[ -n "$DAV_SERVER" ] || DAV_SERVER=radicale
[ -n "$REQUIREMENTS" ] || REQUIREMENTS=release
COMMAND="$1"
if [ -z "$COMMAND" ]; then
    echo "Usage:"
    echo "build.sh run      # run build"
    echo "build.sh install  # install dependencies"
    echo
    echo "Environment variable combinations:"
    echo "BUILD=tests  # install and run tests"
    echo "             # (using Radicale, see .travis.yml for more)"
    echo "BUILD=style  # install and run stylechecker (flake8)"
    echo "BUILD=docs   # install sphinx and build HTML docs"
    exit 1
fi

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
