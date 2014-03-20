#!/bin/sh
echo "The shell is $SHELL"
set -e
pip install --use-mirrors --editable .
pip install --use-mirrors -r requirements.txt
[ -n "$DAV_SERVER" ] || DAV_SERVER=radicale_filesystem

davserver_radicale_filesystem() {
    radicale_deps
}

davserver_radicale_database() {
    radicale_deps
    pip install --use-mirrors sqlalchemy pysqlite
}

radicale_deps() {
    if [ "$REQUIREMENTS" = "release" ]; then
        radicale_pkg="radicale"
    elif [ "$REQUIREMENTS" = "devel" ]; then
        radicale_pkg="git+https://github.com/Kozea/Radicale.git"
    else
        false
    fi
    pip install --use-mirrors werkzeug $radicale_pkg
}

davserver_owncloud() {
    # Maybe tmpfs is mounted on /tmp/, can't harm anyway.
    if [ ! -d ./owncloud-testserver/ ]; then
        git clone --depth=1 \
            https://github.com/untitaker/owncloud-testserver.git \
            /tmp/owncloud-testserver
        ln -s /tmp/owncloud-testserver .
    fi
    cd ./owncloud-testserver/
    sh install.sh
}


davserver_$DAV_SERVER
