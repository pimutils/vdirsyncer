#!/bin/sh
set -e

if [ -z "$RADICALE_BACKEND" ]; then
    echo "Missing RADICALE_BACKEND"
    false
fi

pip install wsgi_intercept radicale

if [ "$RADICALE_BACKEND" = "database" ]; then
    pip install sqlalchemy
fi
