#!/bin/sh
set -xe
distro=$1
distrover=$2
name=vdirsyncer-$distro-$distrover:latest

docker build \
    --build-arg distro=$distro \
    --build-arg distrover=$distrover \
    -t $name \
    -f scripts/dpkg.Dockerfile .
rm -f dist/pkgs/*.deb
docker run $name tar -c -C /vdirsyncer pkgs | tar x -C dist/
package_cloud push pimutils/vdirsyncer/$distro/$distrover --skip-errors dist/pkgs/*.deb
