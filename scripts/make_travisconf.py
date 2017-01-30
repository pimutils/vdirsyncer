import itertools
import json
import sys

python_versions = ("3.3", "3.4", "3.5", "3.6")
latest_python = "3.6"

cfg = {}

cfg['sudo'] = True
cfg['language'] = 'python'

cfg['git'] = {
    'submodules': False
}

cfg['branches'] = {
    'only': ['auto', 'master']
}

cfg['install'] = ["""
. scripts/travis-install.sh;
pip install -U pip;
pip install wheel;
make -e install-dev;
make -e install-$BUILD;
"""]

cfg['script'] = ["make -e $BUILD"]
cfg['after_script'] = ["make -e after-$BUILD"]

matrix = []
cfg['matrix'] = {'include': matrix}

matrix.append({
    'python': latest_python,
    'env': 'BUILD=style BUILD_PRS=true'
})


for python in python_versions:
    if python == latest_python:
        dav_servers = ("radicale", "owncloud", "nextcloud", "baikal",
                       "davical")
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
        build_prs = (
            python == latest_python and
            server_type == 'DAV' and
            server == 'radicale'
        )

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
