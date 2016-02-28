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

from vdirsyncer.cli.utils import coerce_native


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
