from vdirsyncer import exceptions


def test_user_error_problems():
    e = exceptions.UserError('A few problems occured', problems=[
        'Problem one',
        'Problem two',
        'Problem three'
    ])

    assert 'one' in str(e)
    assert 'two' in str(e)
    assert 'three' in str(e)
    assert 'problems occured' in str(e)
