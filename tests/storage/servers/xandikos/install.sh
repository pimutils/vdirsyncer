#!/bin/sh
set -e

pip install wsgi_intercept

if [ "$REQUIREMENTS" = "release" ] || [ "$REQUIREMENTS" = "minimal" ]; then
    # XXX: This is the last version to support Python 3.5
    pip install -U "xandikos==0.0.11"
elif [ "$REQUIREMENTS" = "devel" ]; then
    pip install -U git+https://github.com/jelmer/xandikos
else
    echo "Invalid REQUIREMENTS value"
    false
fi
