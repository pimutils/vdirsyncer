#!/bin/sh

# Travis uses an outdated PyPy, this installs the most recent one.  This
# makes the tests run on Travis' legacy infrastructure, but so be it.
# temporary pyenv installation to get pypy-2.6 before container infra
# upgrade
# Taken from werkzeug, which took it from pyca/cryptography
if [ "$TRAVIS_PYTHON_VERSION" = "pypy" ]; then
    git clone https://github.com/yyuu/pyenv.git ~/.pyenv;
    PYENV_ROOT="$HOME/.pyenv";
    PATH="$PYENV_ROOT/bin:$PATH";
    eval "$(pyenv init -)";
    pyenv install pypy-4.0.1;
    pyenv global pypy-4.0.1;
    python --version;
    pip --version;
fi

# The OS X VM doesn't have any Python support at all
# See https://github.com/travis-ci/travis-ci/issues/2312
if [ "$TRAVIS_OS_NAME" = "osx" ]; then
    brew update
    brew install python3
    virtualenv -p python3 $HOME/osx-py3
    . $HOME/osx-py3/bin/activate
fi
