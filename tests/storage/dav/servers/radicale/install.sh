#!/bin/sh
set -e
[ -n "$REQUIREMENTS" ] || export REQUIREMENTS=release
[ -n "$RADICALE_BACKEND" ] || export RADICALE_BACKEND=filesystem

if [ "$REQUIREMENTS" = "release" ]; then
    radicale_pkg="radicale"
elif [ "$REQUIREMENTS" = "devel" ]; then
    radicale_pkg="git+https://github.com/Kozea/Radicale.git"
else
    echo "Invalid requirements envvar"
    false
fi
pip install wsgi_intercept $radicale_pkg

if [ "$RADICALE_BACKEND" = "database" ]; then
    pip install sqlalchemy
fi
