#!/bin/sh

# The OS X VM doesn't have any Python support at all
# See https://github.com/travis-ci/travis-ci/issues/2312
if [ "$TRAVIS_OS_NAME" = "osx" ]; then
    brew update
    brew install python3
    virtualenv -p python3 $HOME/osx-py3
    . $HOME/osx-py3/bin/activate
fi
