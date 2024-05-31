__all__ = ['Lmpdump']

import os
from itertools import zip_longest
from typing import Union

import pandas as pd

from . import func, logger
from .base import MultiFrames, ReadWrite
from .box import Box


class Lmpdump(ReadWrite, MultiFrames):
    """LAMMPS dump file, snapshots of atoms and various per-atom values"""

    file_sections = [
        # required, section_name, start, end
        (1, 'frame', b'ITEM: TIMESTEP', b'ITEM: TIMESTEP'),
        (1, 'header', b'ITEM: TIMESTEP', b'ITEM: BOX BOUNDS'),
        (1, 'box', b'ITEM: BOX BOUNDS', b'ITEM: ATOMS'),
        (1, 'atoms', b'ITEM: ATOMS', b'ITEM: TIMESTEP'),
    ]

    def scan_byline(self):
        with self.open() as fd:
            fd.seek(self.scanned)  # resume from last read

            for line in fd:
                if line.startswith(b'ITEM: TIMESTEP'):
                    self.end_section('frame')
                    self.end_section('atoms')
                    self.start_section('frame')
                    self.start_section('header')

                elif line.startswith(b'ITEM: BOX BOUNDS'):
                    self.end_section('header')
                    self.start_section('box')

                elif line.startswith(b'ITEM: ATOMS'):
                    self.end_section('box')
                    self.start_section('atoms')

                self.scanned = fd.tell()

    def scan_bychunk(self):
        with self.open() as fd:
            fd.seek(self.scanned)  # resume from last read

            # search for all start/end markers
            _, sects, starts, ends = zip(*self.file_sections)
            patterns = list(dict.fromkeys(starts + ends))
            bytelocs = func.search_in_file(fd, patterns, self.scanned)
            scanned = fd.tell()

            # lookup tables
            matches = dict(zip(patterns, bytelocs))

            # mark start and end of the sections
            for i, (req, sect, start, end) in enumerate(self.file_sections):
                for b0, b1 in zip_longest(matches[start], matches[end]):
                    self.scanned = b1
                    self.end_section(sect)
                    self.scanned = b0
                    self.start_section(sect)
                    self.scanned = b1
                    self.end_section(sect)

            self.scanned = scanned

    def scan(self, method='chunk'):
        logger.debug(f"Scan {self.type} file using '{method}' method.")
        return getattr(self, f"scan_by{method}")()

    def parse(self, section, dtype='dict'):
        if section.name == 'frame':
            output = self.parse(section.section('header'))
            output.update(
                {
                    sect: self.parse(section.section(sect))
                    for sect in ['box', 'atoms']
                }
            )
            # output
            if dtype == 'dict':
                return output
            elif dtype == 'df':
                df = pd.DataFrame(output.pop('atoms'))
                df.attrs.update(output)
                return df

        # ----------------------------------------------

        if section.name == 'header':
            f = section.f
            output = {}
            for line in f:
                if line.startswith(b'ITEM: TIMESTEP'):
                    output['timestep'] = int(f.readline().split()[0])
                elif line.startswith(b'ITEM: NUMBER OF ATOMS'):
                    output['num_atoms'] = int(f.readline())

        elif section.name == 'box':
            f = section.f
            line = f.readline().replace(b'ITEM: BOX BOUNDS', b'')
            box = Box()
            boundaries = line.strip().decode().split()[:3]
            if boundaries:
                box['bx'], box['by'], box['bz'] = boundaries
            box['allow_tilt'] = b'xy xz yz' in line
            tilt = ' 0.0' * (not box['allow_tilt'])
            box_input = ' '.join(
                [f"{f.readline().decode()}{tilt}" for _ in range(3)]
            )
            box.set_input(box_input, typ='lmpdump')
            # output
            if dtype == 'obj':
                return box
            output = {**box.input}

        elif section.name == 'atoms':
            # read column labels
            for line in section:
                col_labels = line.decode().split()[3:]
                break
            # read atoms and create dataframe
            atoms = pd.read_csv(
                section.f,
                sep=r'\s+',
                header=1,
                names=col_labels,
            )
            atoms.sort_index(inplace=True)
            output = {k: atoms[k].values for k in col_labels}

        # output
        if dtype == 'dict':
            return output
        elif dtype == 'df':
            try:
                return pd.DataFrame(output)
            except ValueError:
                return pd.Series(output)

    # -----------------------------------------------

    @classmethod
    def write(
        cls, fpath, data: Union[pd.DataFrame, '__class__'], overwrite=False
    ):
        # multiple frames?
        def get_df():
            if isinstance(data, __class__):
                for fr in data.section('frame'):
                    yield fr.df
            else:
                yield data

        # start writing

        f = cls(fpath, mode='wb').open()

        for df in get_df():
            # header
            timestep = df.attrs.get('timestep', 0)
            f.write(f"ITEM: TIMESTEP\n{timestep}\n".encode())
            f.write(f"ITEM: NUMBER OF ATOMS\n{df.shape[0]}\n".encode())

            # box
            box = Box(df.attrs['box']).output
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

        return os.stat(fpath).st_size
