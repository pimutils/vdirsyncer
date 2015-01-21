# -*- coding: utf-8 -*-

from click.testing import CliRunner

from vdirsyncer.doubleclick import _ctx_stack, click, ctx as global_ctx


def test_simple():
    @click.command()
    @click.pass_context
    def cli(ctx):
        assert global_ctx
        assert ctx.obj is global_ctx.obj
        assert _ctx_stack.top is ctx
        click.echo('hello')

    assert not global_ctx
    runner = CliRunner()
    result = runner.invoke(cli, catch_exceptions=False)
    assert not global_ctx
    assert not result.exception
    assert result.output == 'hello\n'
