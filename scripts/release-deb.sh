#!/bin/sh

set -xe

DISTRO=$1
DISTROVER=$2

NAME="vdirsyncer-${DISTRO}-${DISTROVER}:latest"
CONTEXT="$(mktemp -d)"

python setup.py sdist -d "$CONTEXT"

# Build the package in a container with the right distro version.
docker build \
    --build-arg distro=$DISTRO \
    --build-arg distrover=$DISTROVER \
    -t $NAME \
    -f scripts/dpkg.Dockerfile \
    "$CONTEXT"

# Push the package to packagecloud.
# TODO: Use ~/.packagecloud for CI.
docker run -e PACKAGECLOUD_TOKEN=$PACKAGECLOUD_TOKEN $NAME \
  bash -xec "package_cloud push pimutils/vdirsyncer/$DISTRO/$DISTROVER *.deb"

rm -rf "$CONTEXT"
