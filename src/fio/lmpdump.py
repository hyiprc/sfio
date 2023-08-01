__all__ = ['Lmpdump']

import io
from pathlib import Path
from typing import Union

import pandas as pd

from . import logger
from .base import MultiFrames, ReadWrite, View
from .box import Box


class Lmpdump(ReadWrite, MultiFrames):
    """LAMMPS dump file, snapshots of atoms and various per-atom values"""

    def __init__(self, fpath):
        def splitframes(line):
            return line.decode().startswith('ITEM: TIMESTEP')

        self.fpath = Path(fpath)
        self.fh = self.open(self.fpath, 'rb')
        self._fr = self.init_frames(self.fh, splitframes)

    def __repr__(self):
        view = ' view' * isinstance(self, View)
        return f"<Lmpdump{view} object at {hex(id(self))}, {len(self)} frames>"

    def __str__(self):
        return repr(self)

    # -----------------------------------------------

    def parse(self, fstr):
        f = io.StringIO(fstr)
        out = {}
        Nheader = 0

        # read timestep
        for line in f:
            Nheader += 1
            if line.startswith('ITEM: TIMESTEP'):
                Nheader += 1
                timestep = int(f.readline())
                break

        # read box information
        for line in f:
            Nheader += 1
            if line.startswith('ITEM: BOX BOUNDS'):
                Nheader += 3
                # boundary type
                box = Box()
                box['bx'], box['by'], box['bz'] = line.split()[-3:]
                # box tilt
                if 'xy xz yz' in line:
                    box['allow_tilt'] = True
                tilt = ' 0.0' * (not box['allow_tilt'])
                arg = ' '.join(
                    [f"{f.readline().rstrip()}{tilt}" for _ in range(3)]
                )
                box.set_input(arg, typ='lmpdump')
                break

        # read column labels
        for line in f:
            Nheader += 1
            if line.startswith('ITEM: ATOMS'):
                col_labels = line.split()[3:]
                s_ = {col: i for i, col in enumerate(col_labels)}
                break

        # read atoms and create dataframe
        out = pd.read_csv(f, sep=r'\s+', header=None, names=col_labels)
        out.sort_index(inplace=True)
        out.attrs['filetype'] = 'lmpdump'
        out.attrs['timestep'] = timestep
        out.attrs['box'] = box
        out.attrs['s_'] = s_

        return out

    # -----------------------------------------------

    @classmethod
    def write(
        cls, fpath, data: Union[pd.DataFrame, '__class__'], overwrite=False
    ):
        fpath = Path(fpath)

        # check if fpath exists
        if not overwrite and fpath.exists():
            answer = input(f'Overwrite "{fpath}"? [y/N]')
            if not answer.lower() == 'y':
                logger.info(f'Skip writing, found "{fpath}"')
                return 0

        f = cls.open(fpath, 'ab')

        # multiple frames?
        if isinstance(data, __class__):
            Nfr = len(data)
        else:
            Nfr = 1

        # start writing
        for fr in range(Nfr):
            df = data[fr]

            # header
            timestep = df.attrs.get('timestep', 0)
            f.write(f"ITEM: TIMESTEP\n{timestep}\n".encode())
            f.write(f"ITEM: NUMBER OF ATOMS\n{df.shape[0]}\n".encode())

            # box
            box = df.attrs['box'].output
            bxbybz = ' '.join([box.get(f'b{s}', 'ff') for s in 'xyz'])

            if box.get('allow_tilt', True):
                tilt_str = ' xy xz yz'
                tilt = [f" {box.get(s, 0.0)}" for s in ['xy', 'xz', 'yz']]
            else:
                tilt_str = ''
                tilt = ['', '', '']

            f.write(f"ITEM: BOX BOUNDS{tilt_str} {bxbybz}\n".encode())
            for s, t in zip('xyz', tilt):
                f.write(f"{box[s+'lo']} {box[s+'hi']}{t}\n".encode())

            # atoms
            f.write(b"ITEM: ATOMS id")
            df.to_csv(f, sep=' ', mode='ab')

        f.close()

        return 1
