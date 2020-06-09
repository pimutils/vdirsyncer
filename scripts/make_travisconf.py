#!/usr/bin/env python

import itertools
import json

python_versions = ("3.5", "3.6", "3.7", "3.8")
latest_python = "3.6"

cfg = {}

cfg['sudo'] = True
cfg['dist'] = 'bionic'
cfg['language'] = 'python'
cfg['cache'] = 'pip'

cfg['services'] = ['docker']

cfg['git'] = {
    'submodules': False
}

cfg['branches'] = {
    'only': ['master']
}

cfg['install'] = """
. scripts/travis-install.sh
make -e install-$BUILD
""".strip().splitlines()

cfg['script'] = ["make -e $BUILD"]

matrix = []
cfg['matrix'] = {'include': matrix, 'fast_finish': True}

matrix.append({
    'python': latest_python,
    'env': 'BUILD=style'
})


for python, requirements in itertools.product(
    python_versions,
    # XXX: Use `devel` here for recent python versions:
    ("release", "minimal")
):
    dav_servers = ("radicale", "xandikos")

    matrix.append({
        'python': python,
        'env': f"BUILD=test REQUIREMENTS={requirements}",
    })

    if python == latest_python and requirements == "release":
        dav_servers += ("fastmail",)

    for dav_server in dav_servers:
        job = {
            'python': python,
            'env': ("BUILD=test-storage "
                    f"DAV_SERVER={dav_server} "
                    f"REQUIREMENTS={requirements} ")
        }
        if python == '3.5':
            job['dist'] = 'trusty'

        build_prs = dav_server not in ("fastmail", "davical", "icloud")
        if not build_prs:
            job['if'] = 'NOT (type IN (pull_request))'

        matrix.append(job)

matrix.append({
    'python': latest_python,
    'env': ("BUILD=test "
            "ETESYNC_TESTS=true "
            "REQUIREMENTS=latest")
})

# matrix.append({
#     'language': 'generic',
#     'os': 'osx',
#     'env': 'BUILD=test'
# })

with open('.travis.yml', 'w') as output:
    json.dump(cfg, output, sort_keys=True, indent=2)
