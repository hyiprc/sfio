import pytest

import sfio

box = sfio.Box()


def test_input_assignment():
    # check that box inputs can be assigned
    alpha_before = box['alpha']
    box['alpha'] = 108.0
    alpha_after = box['alpha']
    assert alpha_before != alpha_after
    assert alpha_after == 108.0


def test_invalid_input_assignment():
    # reject assignment of non-box input
    for k in ['a', 'xlo', 'abc']:
        with pytest.raises(KeyError):
            box.input[k] = 1


def test_invalid_input_assignment_dict():
    a_before = box['a']
    box.input.update({'a': 3})
    assert box['a'] == a_before


def test_box_tilt_assignment():
    # upon assignment, tilt remains True for non-orthogonal box
    box.input['allow_tilt'] = False
    assert box.input['allow_tilt'] is True
