import pytest

import fio

template = fio.rootdir / 'data'
sample_files = [
    'gold_fcc.dump',
    'gold_fcc.dump.gz',
    'gold_fcc.atsk',
]


@pytest.fixture(scope="session")
def tmp_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp("data")
    return path


def test_readwrite(tmp_dir):
    for fname in sample_files:
        # read
        f = fio.read(template / fname)
        # write
        if isinstance(f, fio.base.ReadWrite):
            fio.write(tmp_dir / fname, f)
            # read the written file
            fio.read(tmp_dir / fname)


def test_lmpdump_slicing():
    def get_timesteps(df):
        try:
            return df.attrs['timestep']
        except AttributeError:
            return [d.attrs['timestep'] for d in df]

    f = fio.read(template / 'gold_fcc.dump')
    assert f[:] is f

    Nfr = len(f)
    assert Nfr == 4

    # full range slice
    assert f[:Nfr] is f
    assert f[-Nfr:] is f
    assert f[0:Nfr] is f

    # single frame slice
    assert get_timesteps(f[1:2]) == 1000
    assert get_timesteps(f[-1:-2:-1]) == 3000

    # slice
    assert get_timesteps(f[1:3]) == [1000, 2000]

    # slice of a view
    assert get_timesteps(f[1:][:2]) == [1000, 2000]

    # slice of a view that is out of range
    with pytest.raises(IndexError):
        f[1:][:8]

    # slice that is out of range
    with pytest.raises(IndexError):
        f[1:10]
    with pytest.raises(IndexError):
        f[1:-5]

    # reverse
    assert get_timesteps(f[Nfr - 1 :: -1]) == [3000, 2000, 1000, 0]
    assert get_timesteps(f[Nfr - 1 : 0 : -1]) == [3000, 2000, 1000]
    assert get_timesteps(f[::-1]) == [3000, 2000, 1000, 0]
    assert get_timesteps(f[2::-1]) == [2000, 1000, 0]
    assert get_timesteps(f[-1::-1]) == [3000, 2000, 1000, 0]

    # indexing
    assert get_timesteps(f[[0]]) == 0
    assert get_timesteps(f[[0, 3, 1]]) == [0, 3000, 1000]
    assert f[[0, 1, 2, 3]] is f

    # indexing out of range
    with pytest.raises(IndexError):
        f[[0, 5, 2, 3]]
