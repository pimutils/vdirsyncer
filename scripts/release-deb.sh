#!/bin/sh

set -xeu

SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")

# E.g.: debian, ubuntu
DISTRO=${DISTRO:1}
# E.g.: bullseye, bookwork
DISTROVER=${DISTROVER:2}
CONTAINER_NAME="vdirsyncer-${DISTRO}-${DISTROVER}"
CONTEXT="$(mktemp -d)"

DEST_DIR="$SCRIPT_DIR/../$DISTRO-$DISTROVER"

cleanup() {
  rm -rf "$CONTEXT"
}
trap cleanup EXIT

# Prepare files.
cp scripts/_build_deb_in_container.bash "$CONTEXT"
python setup.py sdist -d "$CONTEXT"

docker run -it \
  --name "$CONTAINER_NAME" \
  --volume "$CONTEXT:/source" \
  "$DISTRO:$DISTROVER" \
  bash /source/_build_deb_in_container.bash

# Keep around the package filename.
PACKAGE=$(ls "$CONTEXT"/*.deb)
PACKAGE=$(basename "$PACKAGE")

# Save the build deb files.
mkdir -p "$DEST_DIR"
cp "$CONTEXT"/*.deb "$DEST_DIR"

echo Build complete! 🤖

# Packagecloud uses some internal IDs for each distro.
# Extract the one for the distro we're publishing.
DISTRO_ID=$(
  curl -s \
  https://"$PACKAGECLOUD_TOKEN":@packagecloud.io/api/v1/distributions.json | \
  jq '.deb | .[] | select(.index_name=="'"$DISTRO"'") | .versions | .[] | select(.index_name=="'"$DISTROVER"'") | .id'
)

# Actually push the package.
curl \
  -F "package[distro_version_id]=$DISTRO_ID" \
  -F "package[package_file]=@$DEST_DIR/$PACKAGE" \
  https://"$PACKAGECLOUD_TOKEN":@packagecloud.io/api/v1/repos/pimutils/vdirsyncer/packages.json

echo Done! ✨
