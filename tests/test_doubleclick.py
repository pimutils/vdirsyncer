# -*- coding: utf-8 -*-
'''
    tests.test_doubleclick
    ~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 Markus Unterwaditzer & contributors
    :license: MIT, see LICENSE for more details.
'''
from click.testing import CliRunner

from vdirsyncer.doubleclick import _ctx_stack, click, ctx as global_ctx


def test_simple():
    @click.command()
    @click.pass_context
    def cli(ctx):
        assert global_ctx
        assert _ctx_stack.top is ctx

    assert not global_ctx
    runner = CliRunner()
    runner.invoke(cli)
