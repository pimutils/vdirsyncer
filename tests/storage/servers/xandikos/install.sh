#!/bin/sh
set -e

pip install wsgi_intercept

if [ "$REQUIREMENTS" = "release" ] || [ "$REQUIREMENTS" = "minimal" ]; then
    pip install -U xandikos
elif [ "$REQUIREMENTS" = "devel" ]; then
    pip install -U git+https://github.com/jelmer/xandikos
else
    echo "Invalid REQUIREMENTS value"
    false
fi
