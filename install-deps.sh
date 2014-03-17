#!/bin/sh
pip install --use-mirrors .
pip install --use-mirrors -r requirements.txt
[[ -z "$DAV_SERVER" ]] && DAV_SERVER=radicale
[[ -z "$RADICALE_STORAGE" ]] && RADICALE_STORAGE=filesystem

davserver_radicale() {
    pip install --use-mirrors radicale
    radicale_deps
}

davserver_radicale_git() {
    pip install git+https://github.com/Kozea/Radicale.git
    radicale_deps
}

radicale_deps() { radicale_storage_$RADICALE_STORAGE; }

radicale_storage_database() { pip install --use-mirrors sqlalchemy pysqlite; }
radicale_storage_filesystem() { true; }


davserver_owncloud() {
    pip install paste
    git clone git@github.com:untitaker/owncloud-testserver.git
    cd ./owncloud-testserver/
    sh install.sh
}


davserver_$DAV_SERVER
