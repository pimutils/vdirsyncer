import itertools
import json
import sys


def script(x):
    return """
if [ "$BUILD_PRS" = "true" ] || [ "$TRAVIS_PULL_REQUEST" = "false" ]; then
    {}
fi
    """.strip().format(x.strip())

cfg = {}

cfg['sudo'] = True
cfg['language'] = 'python'

cfg['git'] = {
    'submodules': False
}

cfg['branches'] = {
    'only': ['auto', 'master']
}

cfg['install'] = [script("""
    . scripts/travis-install.sh;
    pip install -U pip;
    pip install wheel;
    make -e install-dev;
    make -e install-$BUILD;
""")]

cfg['script'] = [script("""
    make -e $BUILD
""")]

matrix = []
cfg['matrix'] = {'include': matrix}

matrix.append({
    'language': 'generic',
    'os': 'osx',
    'env': 'BUILD=test'
})

json.dump(cfg, sys.stdout, sort_keys=True, indent=2)
