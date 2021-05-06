from vdirsyncer import exceptions


def test_user_error_problems():
    e = exceptions.UserError(
        "A few problems occurred",
        problems=["Problem one", "Problem two", "Problem three"],
    )

    assert "one" in str(e)
    assert "two" in str(e)
    assert "three" in str(e)
    assert "problems occurred" in str(e)
