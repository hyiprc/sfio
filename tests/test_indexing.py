import pytest

import sfio
import sfio.base

sfio.logger.level = 999


def test_indexing():
    get_index = sfio.base.Sectioned.get_index
    length = 100

    with pytest.raises(SystemExit):
        get_index(length + 1, length)
    with pytest.raises(SystemExit):
        get_index(length, length)
    assert get_index(length - 1, length) == length - 1
    assert get_index(0, length) == 0
    assert get_index(-0, length) == 0
    assert get_index(-1, length) == length - 1
    assert get_index(-length, length) == 0
    with pytest.raises(SystemExit):
        get_index(-length - 1, length)
    with pytest.raises(SystemExit):
        get_index(-length - 2, length)

    with pytest.raises(SystemExit):
        get_index(length + 1, length, right=True)
    assert get_index(length, length, right=True) == length
    assert get_index(length - 1, length, right=True) == length - 1
    assert get_index(0, length, right=True) == 0
    assert get_index(-0, length, right=True) == 0
    assert get_index(-1, length, right=True) == length
    assert get_index(-length, length, right=True) == 1
    assert get_index(-length - 1, length, right=True) == 0
    with pytest.raises(SystemExit):
        get_index(-length - 2, length, right=True)
