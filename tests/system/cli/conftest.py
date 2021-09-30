from textwrap import dedent

import pytest
from click.testing import CliRunner

import vdirsyncer.cli as cli


class _CustomRunner:
    def __init__(self, tmpdir):
        self.tmpdir = tmpdir
        self.cfg = tmpdir.join("config")
        self.runner = CliRunner()

    def invoke(self, args, env=None, **kwargs):
        env = env or {}
        env.setdefault("VDIRSYNCER_CONFIG", str(self.cfg))
        return self.runner.invoke(cli.app, args, env=env, **kwargs)

    def write_with_general(self, data):
        self.cfg.write(
            dedent(
                """
        [general]
        status_path = "{}/status/"
        """
            ).format(str(self.tmpdir))
        )
        self.cfg.write(data, mode="a")


@pytest.fixture
def runner(tmpdir):
    return _CustomRunner(tmpdir)
