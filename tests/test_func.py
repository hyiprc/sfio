import pytest

import sfio.func as func


@pytest.mark.parametrize(
    'inputs, expected_output',
    [
        # iterables
        ([[1], {1}, (1), [2, 3], {4, 5}, (6, 7)], [1, 1, 1, 2, 3, 4, 5, 6, 7]),
        # strings and bytes
        (['a', b'a', 'string', b'bytes'], ['a', b'a', 'string', b'bytes']),
        # non-iterables
        ([None, True, 1], [None, True, 1]),
        # generator-like
        ([range(3), [i**2 for i in range(3)]], [0, 1, 2, 0, 1, 4]),
        # deep nesting
        ([1, [1], [[[1]]], [2, [2], [[2]]]], [1, 1, 1, 2, 2, 2]),
        ([((((4,),),),), [5, [6, 7, (8, 9)]]], [4, 5, 6, 7, 8, 9]),
    ],
)
def test_flatten(inputs, expected_output):
    assert list(func.flatten(inputs)) == expected_output
