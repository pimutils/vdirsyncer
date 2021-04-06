#!/usr/bin/env python
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

builds = [
    {
        "BUILD": "style",
        "REQUIREMENTS": "release",
        "DAV_SERVER": "skip",
    },
    {
        "ETESYNC_TESTS": "true",
        "BUILD": "test",
        "REQUIREMENTS": "release",
        "DAV_SERVER": "skip",
    },
]

# XXX: Use `devel` here for recent python versions:
for requirements in ("release", "minimal"):
    # XXX: `fastmail` has been left out here:
    dav_servers = ("radicale", "xandikos")

    builds.append(
        {
            "BUILD": "test",
            "REQUIREMENTS": requirements,
            "DAV_SERVER": "skip",
        },
    )

    for dav_server in dav_servers:
        job = {
            "BUILD": "test-storage",
            "REQUIREMENTS": requirements,
            "DAV_SERVER": dav_server,
        }


with open(REPO_ROOT / "scripts" / "tests.template") as f:
    template = f.read()

# TODO: Delete previous ones...

for i, build in enumerate(builds):
    with open(REPO_ROOT / ".builds" / f"{i}.yaml", "w") as f:
        f.write(template.format(**build))
