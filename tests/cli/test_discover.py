from textwrap import dedent


def test_discover_command(tmpdir, runner):
    runner.write_with_general(dedent('''
    [storage foo]
    type = filesystem
    path = {0}/foo/
    fileext = .txt

    [storage bar]
    type = filesystem
    path = {0}/bar/
    fileext = .txt

    [pair foobar]
    a = foo
    b = bar
    collections = ["from a"]
    ''').format(str(tmpdir)))

    foo = tmpdir.mkdir('foo')
    bar = tmpdir.mkdir('bar')

    for x in 'abc':
        foo.mkdir(x)
        bar.mkdir(x)
    bar.mkdir('d')

    result = runner.invoke(['sync'])
    assert not result.exception
    lines = result.output.splitlines()
    assert lines[0].startswith('Discovering')
    assert 'Syncing foobar/a' in lines
    assert 'Syncing foobar/b' in lines
    assert 'Syncing foobar/c' in lines
    assert 'Syncing foobar/d' not in lines

    foo.mkdir('d')
    result = runner.invoke(['sync'])
    assert not result.exception
    assert 'Syncing foobar/a' in lines
    assert 'Syncing foobar/b' in lines
    assert 'Syncing foobar/c' in lines
    assert 'Syncing foobar/d' not in result.output

    result = runner.invoke(['discover'])
    assert not result.exception

    result = runner.invoke(['sync'])
    assert not result.exception
    assert 'Syncing foobar/a' in lines
    assert 'Syncing foobar/b' in lines
    assert 'Syncing foobar/c' in lines
    assert 'Syncing foobar/d' in result.output

    # Check for redundant data that is already in the config. This avoids
    # copying passwords from the config too.
    assert 'fileext' not in tmpdir \
        .join('status') \
        .join('foobar.collections') \
        .read()
