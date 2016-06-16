import itertools
import json
import sys


cfg = {}

cfg['sudo'] = True
cfg['language'] = 'python'

cfg['git'] = {
    'submodules': False
}

cfg['branches'] = {
    'only': ['auto', 'master']
}

cfg['install'] = [
    ". scripts/travis-install.sh",
    "make -e install-dev",
    "make -e install-$BUILD"
]

cfg['script'] = "make -e $BUILD"

matrix = []
cfg['matrix'] = {'include': matrix}

for python in ("2.7", "3.3", "3.4", "3.5", "pypy"):
    matrix.append({
        'python': python,
        'env': 'BUILD=style'
    })

    if python == "3.5":
        dav_servers = ("radicale", "owncloud", "baikal", "davical")
        rs_servers = ("mysteryshack",)
    elif python == "2.7":
        dav_servers = ("owncloud", "baikal", "davical")
        rs_servers = ("mysteryshack",)
    elif python == "pypy":
        dav_servers = ()
        rs_servers = ()
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
        matrix.append({
            'python': python,
            'env': ("BUILD=test "
                    "{server_type}_SERVER={server} "
                    "REQUIREMENTS={requirements}"
                    .format(server_type=server_type,
                            server=server,
                            requirements=requirements))
        })

matrix.append({
    'language': 'generic',
    'os': 'osx',
    'env': 'BUILD=test'
})

json.dump(cfg, sys.stdout, sort_keys=True, indent=2)
