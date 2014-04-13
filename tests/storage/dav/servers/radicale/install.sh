#!/bin/sh
set -e

if [ "$REQUIREMENTS" = "release" ]; then
    radicale_pkg="radicale"
elif [ "$REQUIREMENTS" = "devel" ]; then
    radicale_pkg="git+https://github.com/Kozea/Radicale.git"
else
    echo "Invalid requirements envvar"
    false
fi
pip install werkzeug $radicale_pkg

if [ "$RADICALE_BACKEND" = "database" ]; then
    pip install sqlalchemy pysqlite
fi
