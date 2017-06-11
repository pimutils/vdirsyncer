#!/bin/sh
set -ex
cd "$(dirname "$0")"
. ./variables.sh

if [ "$CI" = "true" ]; then
    curl https://sh.rustup.rs/ | sh -s -- -y
fi

if [ ! -d mysteryshack ]; then
    git clone https://github.com/untitaker/mysteryshack
fi

pip install pytest-xprocess

cd mysteryshack
make libsodium
make debug-build  # such that first test doesn't hang too long w/o output
