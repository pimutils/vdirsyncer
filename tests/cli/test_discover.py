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

    result = runner.invoke(['discover'])
    assert not result.exception

    foo.mkdir('d')
    result = runner.invoke(['sync'])
    assert not result.exception
    lines = result.output.splitlines()
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


def test_discover_on_unsupported_storage(tmpdir, runner):
    runner.write_with_general(dedent('''
    [storage foo]
    type = http
    url = https://example.com/foo.ics

    [storage bar]
    type = memory
    fileext = .txt

    [pair foobar]
    a = foo
    b = bar
    collections = ["from a"]
    ''').format(str(tmpdir)))

    result = runner.invoke(['discover'])
    assert result.exception
    assert 'doesn\'t support collection discovery' in result.output


def test_discover_different_collection_names(tmpdir, runner):
    foo = tmpdir.mkdir('foo')
    bar = tmpdir.mkdir('bar')
    runner.write_with_general(dedent('''
    [storage foo]
    type = filesystem
    fileext = .txt
    path = {foo}

    [storage bar]
    type = filesystem
    fileext = .txt
    path = {bar}

    [pair foobar]
    a = foo
    b = bar
    collections = [
        ["coll1", "coll_a1", "coll_b1"],
        "coll2"
     ]
    ''').format(foo=str(foo), bar=str(bar)))

    result = runner.invoke(['discover'], input='y\n' * 6)
    assert not result.exception

    coll_a1 = foo.join('coll_a1')
    coll_b1 = bar.join('coll_b1')

    assert coll_a1.exists()
    assert coll_b1.exists()

    result = runner.invoke(['sync'])
    assert not result.exception

    foo_txt = coll_a1.join('foo.txt')
    foo_txt.write('BEGIN:VCALENDAR\nUID:foo\nEND:VCALENDAR')

    result = runner.invoke(['sync'])
    assert not result.exception

    assert foo_txt.exists()
    assert coll_b1.join('foo.txt').exists()


def test_discover_direct_path(tmpdir, runner):
    foo = tmpdir.join('foo')
    bar = tmpdir.join('bar')

    runner.write_with_general(dedent('''
    [storage foo]
    type = filesystem
    fileext = .txt
    path = {foo}

    [storage bar]
    type = filesystem
    fileext = .txt
    path = {bar}

    [pair foobar]
    a = foo
    b = bar
    collections = null
    ''').format(foo=str(foo), bar=str(bar)))

    result = runner.invoke(['discover'])
    assert not result.exception

    result = runner.invoke(['sync'], input='y\n' * 2)
    assert not result.exception

    assert foo.exists()
    assert bar.exists()
