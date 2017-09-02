#!/bin/sh
set -xe
distro=$1
distrover=$2
name=vdirsyncer-$distro-$distrover:latest
context="$(mktemp -d)"

python setup.py sdist -d "$context"
cp scripts/dpkg.Dockerfile "$context/Dockerfile"

docker build \
    --build-arg distro=$distro \
    --build-arg distrover=$distrover \
    -t $name \
    "$context"

mkdir -p dist/
docker run $name tar -c -C /vdirsyncer pkgs | tar x -C "$context"
package_cloud push pimutils/vdirsyncer/$distro/$distrover $context/pkgs/*.deb
rm -rf "$context"
