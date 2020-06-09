#!/usr/bin/env python
import itertools
import json

python_versions = ["3.7", "3.8"]

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
    'python': python_versions[0],
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

    if python == python_versions[0] and requirements == "release":
        dav_servers += ("fastmail",)

    for dav_server in dav_servers:
        job = {
            'python': python,
            'env': ("BUILD=test-storage "
                    f"DAV_SERVER={dav_server} "
                    f"REQUIREMENTS={requirements} ")
        }

        build_prs = dav_server not in ("fastmail", "davical", "icloud")
        if not build_prs:
            job['if'] = 'NOT (type IN (pull_request))'

        matrix.append(job)

matrix.append({
    'python': python_versions[0],
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
