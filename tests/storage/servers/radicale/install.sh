#!/bin/sh
set -e

if [ "$REQUIREMENTS" = "release" ] || [ "$REQUIREMENTS" = "minimal" ]; then
    radicale_pkg="radicale"
elif [ "$REQUIREMENTS" = "devel" ]; then
    radicale_pkg="git+https://github.com/Kozea/Radicale.git"
else
    echo "Invalid requirements envvar"
    false
fi
pip install wsgi_intercept $radicale_pkg
