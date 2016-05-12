from hypothesis import given
from hypothesis.strategies import (
    binary,
    booleans,
    complex_numbers,
    floats,
    integers,
    none,
    one_of,
    text
)


from vdirsyncer import exceptions
from vdirsyncer.cli.utils import coerce_native, handle_cli_error


@given(one_of(
    binary(),
    booleans(),
    complex_numbers(),
    floats(),
    integers(),
    none(),
    text()
))
def test_coerce_native_fuzzing(s):
    coerce_native(s)


def test_handle_cli_error(capsys):
    try:
        raise exceptions.InvalidResponse('ayy lmao')
    except:
        handle_cli_error()

    out, err = capsys.readouterr()
    assert 'returned something vdirsyncer doesn\'t understand' in err
    assert 'ayy lmao' in err
