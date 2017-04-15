#!/bin/sh
set -ex
cd "$(dirname "$0")"
. ./variables.sh

if [ "$CI" = "true" ]; then
    curl -sL https://static.rust-lang.org/rustup.sh -o ~/rust-installer/rustup.sh
    sh ~/rust-installer/rustup.sh --prefix=~/rust --spec=stable -y --disable-sudo 2> /dev/null
fi

if [ ! -d mysteryshack ]; then
    git clone https://github.com/untitaker/mysteryshack
fi

pip install pytest-xprocess

cd mysteryshack
make debug-build  # such that first test doesn't hang too long w/o output
