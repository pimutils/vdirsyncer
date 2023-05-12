#!/bin/bash
#
# This script is mean to be run inside a dedicated container,
# and not interatively.

set -ex

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y build-essential fakeroot debhelper git
apt-get install -y python3-all python3-pip python3-venv
apt-get install -y ruby ruby-dev

pip3 install virtualenv virtualenv-tools3
virtualenv -p python3 /vdirsyncer/env/

gem install fpm

# See https://github.com/jordansissel/fpm/issues/1106#issuecomment-461678970
pip3 uninstall -y virtualenv
echo 'python3 -m venv "$@"' > /usr/local/bin/virtualenv
chmod +x /usr/local/bin/virtualenv

cp -r /source/ /vdirsyncer/vdirsyncer/
cd /vdirsyncer/vdirsyncer/ || exit 2
mkdir /vdirsyncer/pkgs/

basename -- *.tar.gz .tar.gz | cut -d'-' -f2 | sed -e 's/\.dev/~/g' | tee version
# XXX: Do I really not want google support included?
(echo -n *.tar.gz; echo '[google]') | tee requirements.txt
fpm --verbose \
  --input-type virtualenv \
  --output-type deb \
  --name "vdirsyncer-latest" \
  --version "$(cat version)" \
  --prefix /opt/venvs/vdirsyncer-latest \
  --depends python3 \
  requirements.txt

mv /vdirsyncer/vdirsyncer/*.deb /vdirsyncer/pkgs/

cd /vdirsyncer/pkgs/
dpkg -i -- *.deb

# Check that it works:
LC_ALL=C.UTF-8 LANG=C.UTF-8 /opt/venvs/vdirsyncer-latest/bin/vdirsyncer --version

cp -- *.deb /source/
