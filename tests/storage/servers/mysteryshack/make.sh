#!/bin/sh
set -e

# pytest-xprocess doesn't allow us to CD into a particular directory before
# launching a command, so we do it here.
cd "$(dirname "$0")"
. ./variables.sh
cd mysteryshack
exec make "$@"
