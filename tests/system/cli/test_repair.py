from textwrap import dedent

import pytest


@pytest.fixture
def storage(tmpdir, runner):
    runner.write_with_general(
        dedent(
            """
    [storage foo]
    type = "filesystem"
    path = "{base}/foo/"
    fileext = ".txt"
    """
        ).format(base=str(tmpdir))
    )

    return tmpdir.mkdir("foo")


@pytest.mark.parametrize("collection", [None, "foocoll"])
def test_basic(storage, runner, collection):
    if collection is not None:
        storage = storage.mkdir(collection)
        collection_arg = f"foo/{collection}"
    else:
        collection_arg = "foo"

    argv = ["repair", collection_arg]

    result = runner.invoke(argv, input="y")
    assert not result.exception

    storage.join("item.txt").write("BEGIN:VCARD\nEND:VCARD")
    storage.join("toobroken.txt").write("")

    result = runner.invoke(argv, input="y")
    assert not result.exception
    assert "No UID" in result.output
    assert "'toobroken.txt' is malformed beyond repair" in result.output
    (new_fname,) = [x for x in storage.listdir() if "toobroken" not in str(x)]
    assert "UID:" in new_fname.read()


@pytest.mark.parametrize("repair_uids", [None, True, False])
def test_repair_uids(storage, runner, repair_uids):
    f = storage.join("baduid.txt")
    orig_f = "BEGIN:VCARD\nUID:!!!!!\nEND:VCARD"
    f.write(orig_f)

    if repair_uids is None:
        opt = []
    elif repair_uids:
        opt = ["--repair-unsafe-uid"]
    else:
        opt = ["--no-repair-unsafe-uid"]

    result = runner.invoke(["repair"] + opt + ["foo"], input="y")
    assert not result.exception

    if repair_uids:
        assert "UID or href is unsafe, assigning random UID" in result.output
        assert not f.exists()
        (new_f,) = storage.listdir()
        s = new_f.read()

        assert s.startswith("BEGIN:VCARD")
        assert s.endswith("END:VCARD")
        assert s != orig_f
    else:
        assert (
            "UID may cause problems, add --repair-unsafe-uid to repair."
            in result.output
        )
        assert f.read() == orig_f
