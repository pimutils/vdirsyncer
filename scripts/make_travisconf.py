import itertools
import json
import sys

python_versions = ("3.3", "3.4", "3.5", "3.6")
latest_python = "3.6"

cfg = {}

cfg['sudo'] = True
cfg['dist'] = 'trusty'
cfg['language'] = 'python'
cfg['cache'] = 'pip'

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

script = """
if [ "$TRAVIS_PULL_REQUEST" = "false" ] || [ "$BUILD_PRS" != "false" ];
then {};
fi""".format

cfg['script'] = [script("make -e $BUILD")]

matrix = []
cfg['matrix'] = {'include': matrix}

matrix.append({
    'python': latest_python,
    'env': 'BUILD=style BUILD_PRS=true'
})


for python, requirements in itertools.product(python_versions,
                                              ("devel", "release", "minimal")):
    dav_servers = ("radicale", "xandikos")

    if python == latest_python and requirements == "release":
        dav_servers += ("owncloud", "nextcloud", "baikal", "davical", "icloud",
                        "fastmail")

    for dav_server in dav_servers:
        build_prs = dav_server not in ("fastmail", "davical", "icloud")
        matrix.append({
            'python': python,
            'env': ("BUILD=test "
                    "DAV_SERVER={dav_server} "
                    "REQUIREMENTS={requirements} "
                    "BUILD_PRS={build_prs} "
                    .format(dav_server=dav_server,
                            requirements=requirements,
                            build_prs=build_prs and "true" or "false"))
        })

matrix.append({
    'python': latest_python,
    'env': ("BUILD=test "
            "ETESYNC_TESTS=true "
            "REQUIREMENTS=latest "
            "BUILD_PRS=true ")
})

matrix.append({
    'language': 'generic',
    'os': 'osx',
    'env': 'BUILD=test BUILD_PRS=true'
})

json.dump(cfg, sys.stdout, sort_keys=True, indent=2)
