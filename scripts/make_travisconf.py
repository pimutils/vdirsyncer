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

cfg['sudo'] = False
cfg['language'] = 'python'
cfg['dist'] = 'trusty'

cfg['addons'] = {
    'apt': {
        'packages': [
            'php5',
            'php5-cli',
            'php5-gd',
            'php5-json',
            'php5-sqlite',
            'php5-curl',
            'php5-intl',
            'php5-mcrypt',
            'php5-imagick'
        ]
    }
}

cfg['branches'] = {
    'only': ['auto', 'master', 'containers']
}

cfg['install'] = [script("""
    . scripts/travis-install.sh;
    pip install -U pip;
    pip install wheel;
    make -e install-dev;
    make -e install-$BUILD;
""")]

cfg['script'] = [script("""
    make -e $BUILD || (cat .xprocess/owncloud_server/xprocess.log && false)
""")]

matrix = []
cfg['matrix'] = {'include': matrix}

for python in ("2.7", "3.3", "3.4", "3.5", "pypy"):
    matrix.append({
        'python': python,
        'env': 'BUILD=style BUILD_PRS=true'
    })

    if python in ("2.7", "3.5"):
        dav_servers = ("radicale", "owncloud", "baikal", "davical")
        rs_servers = ("mysteryshack",)
    else:
        dav_servers = ("radicale",)
        rs_servers = ()

    for (server_type, server), requirements in itertools.product(
        itertools.chain(
            (("REMOTESTORAGE", x) for x in rs_servers),
            (("DAV", x) for x in dav_servers)
        ),
        ("devel", "release", "minimal")
    ):
        build_prs = (
            python in ("2.7", "3.5") and
            server_type == 'DAV' and
            server == 'radicale'
        )

        if server != "owncloud" or python != "3.5":
            continue

        matrix.append({
            'python': python,
            'env': ("BUILD=test "
                    "{server_type}_SERVER={server} "
                    "REQUIREMENTS={requirements} "
                    "BUILD_PRS={build_prs}"
                    .format(server_type=server_type,
                            server=server,
                            requirements=requirements,
                            build_prs='true' if build_prs else 'false'))
        })

matrix.append({
    'language': 'generic',
    'os': 'osx',
    'env': 'BUILD=test'
})

json.dump(cfg, sys.stdout, sort_keys=True, indent=2)
