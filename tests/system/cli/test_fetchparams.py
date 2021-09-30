from textwrap import dedent


def test_get_password_from_command(tmpdir, runner):
    runner.write_with_general(
        dedent(
            """
        [pair foobar]
        a = "foo"
        b = "bar"
        collections = ["a", "b", "c"]

        [storage foo]
        type = "filesystem"
        path = "{base}/foo/"
        fileext.fetch = ["command", "echo", ".txt"]

        [storage bar]
        type = "filesystem"
        path = "{base}/bar/"
        fileext.fetch = ["prompt", "Fileext for bar"]
    """.format(
                base=str(tmpdir)
            )
        )
    )

    foo = tmpdir.ensure("foo", dir=True)
    foo.ensure("a", dir=True)
    foo.ensure("b", dir=True)
    foo.ensure("c", dir=True)
    bar = tmpdir.ensure("bar", dir=True)
    bar.ensure("a", dir=True)
    bar.ensure("b", dir=True)
    bar.ensure("c", dir=True)

    result = runner.invoke(["discover"], input=".asdf\n")
    assert not result.exception
    status = tmpdir.join("status").join("foobar.collections").read()
    assert "foo" in status
    assert "bar" in status
    assert "asdf" not in status
    assert "txt" not in status

    foo.join("a").join("foo.txt").write("BEGIN:VCARD\nUID:foo\nEND:VCARD")
    result = runner.invoke(["sync"], input=".asdf\n")
    assert not result.exception
    assert [x.basename for x in bar.join("a").listdir()] == ["foo.asdf"]
