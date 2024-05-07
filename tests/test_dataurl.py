from pathlib import Path

import numpy as np

import sfio.dataurl

cases = [
    np.inf,
    None,
    {1: 2, 3: 4}.keys(),
    Path('/home/henry/a'),
    [[1, 2, 3, [3, 'd', slice(1, 6, 3)]], [4, 5, 6]],
    tuple([slice(1, 6, 3), [set(['s', 4, 7.8]), 2], 's']),
    tuple([1, 2, 3]),
    b'a',
    set([1, 2, 3]),
    np.array([[1 + 2j, 2, 3.4, 5], [1, 2, 3, 4]]),
    # no type conversion within dict, do not include ndarray, byte
    {
        1: slice(1, 6, 3),
        2: [
            set(['s', (4, 'a'), 7.8]),
            [
                [True, False, None],
                2,
                (Path('/home/test/a'), 2),
            ],
            'astring [1,6,3]',
        ],
    },
]


# ----------------------------------


def eye(b):
    return b


def byte_to_str(b):
    return b.decode()


# convert type before comparing
cvt = {
    'dict_keys': list,
    'bytes': byte_to_str,
}


# ----------------------------------


def compare1(a, b):
    return a == b


def compare2(a, b):
    return a is b


def compare3(a, b):
    return np.array_equal(a, b)


# method of comparison
checks = {
    'NoneType': compare2,
    'ndarray': compare3,
}

# ----------------------------------


def test_encode_then_decode():
    for case in cases:
        typ = type(case).__name__
        check = checks.get(typ, compare1)
        target = cvt.get(typ, eye)(case)

        datastr = sfio.dataurl.encode(case)
        if isinstance(datastr, dict):
            print('\n', datastr)
            print('\n', sfio.dataurl.convert_old_dict_style(datastr))
        decoded = sfio.dataurl.decode(datastr)

        assert check(target, decoded)


def convert_old_style():
    old_style = (
        {
            "__type__": "numpy.ndarray",
            "__data__": {
                "dtype": "float32",
                "shape": [21, 2],
                "array": "zcxMvQPMWsDsUTi9CK9bwArXI73Jc1zAKVwPvSocXcCPwvW8ZaddwM3MzLyYGV7ACtejvAlxXsCPwnW8ca1ewArXI7xO017ACteju2ngXsAAAAAAa9dewArXozvHuV7ACtcjPKGGXsCPwnU8HT1ewArXozyC4l3AzczMPFh1XcCPwvU8BvZcwClcDz05ZFzACtcjPW7DW8DsUTg9iBJbwM3MTD1/UFrA",
            },
        },
    )

    target = 'data:python/numpy.ndarray:float32:shape=21x2;base64,zcxMvQPMWsDsUTi9CK9bwArXI73Jc1zAKVwPvSocXcCPwvW8ZaddwM3MzLyYGV7ACtejvAlxXsCPwnW8ca1ewArXI7xO017ACteju2ngXsAAAAAAa9dewArXozvHuV7ACtcjPKGGXsCPwnU8HT1ewArXozyC4l3AzczMPFh1XcCPwvU8BvZcwClcDz05ZFzACtcjPW7DW8DsUTg9iBJbwM3MTD1/UFrA'

    new_style = sfio.dataurl.convert_old_dict_style(old_style)

    assert new_style == target
