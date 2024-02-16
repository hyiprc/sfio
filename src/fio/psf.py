__all__ = ['Psf']

import pandas as pd

from .base import ReadOnly, Sectioned


class Psf(ReadOnly, Sectioned):
    """X-PLOR Protein Structure Files"""

    sect_topo = ['bonds', 'angles', 'dihedrals', 'impropers']

    def scan(self, size: int = -1):
        sections = [
            # required?, section, pattern
            (1, 'header', 'PSF'),
            (1, 'atoms', b' !NATOM'),
            (0, 'bonds', b' !NBOND'),
            (0, 'angles', b' !NTHETA'),
            (0, 'dihedrals', b' !NPHI'),
            (0, 'impropers', b' !NIMPHI'),
            (0, 'H_donors', b' !NDON'),
            (0, 'H_acceptors', b' !NACC'),
            (0, 'non_bonded_exclusion', b' !NNB'),
            (0, 'unknown', b' !NGRP'),
        ]
        with self.open() as fd:
            fd.seek(self.scanned)  # resume from last read

            if not self.scanned:
                self.start_section('header')

            for line in fd:
                if self.scanned >= size > 0:
                    break

                for i, (required, sect, pattern) in enumerate(sections[1:]):
                    if pattern is not None and pattern in line:
                        for _, prev_sect, _ in sections[: i + 1]:
                            self.end_section(prev_sect)
                            sections.pop(0)
                        self.start_section(sect)
                        break
                    if required and sect not in self.sections:
                        break

                self.scanned = fd.tell()

    def parse(self, section, dtype='dict'):
        if section.name == 'atoms':
            # get column labels
            col_labels = {
                'id': '%8d',
                'segname': '%-4s',
                'resid': '%-4d',
                'resname': '%-4s',
                'name': '%-4s',
                'type': '%-4s',
                'q': '%10.6f',
                'mass': '%13.4f',
                'flag': '%d',
            }
            map_fmt = {'d': int, 'f': float, 's': str}
            rfmt = {k: map_fmt[col_labels[k][-1]] for k in col_labels}
            # read atoms and create dataframe
            atoms = pd.read_csv(
                section.f, sep=r'\s+', header=0, names=col_labels.keys()
            ).astype(rfmt)
            atoms.sort_index(inplace=True)
            output = {k: atoms[k].values for k in col_labels.keys()}

        elif section.name in self.sect_topo:
            # get column labels
            N = min(self.sect_topo.index(section.name) + 2, 4)
            col_labels = [f'atom-{i+1}' for i in range(N)]
            # read bonds/angles/dihedrals/impropers and create dataframe
            names = [str(i) for i in range(N * (9 // N))]
            topos = pd.read_csv(section.f, sep=r'\s+', skiprows=1, names=names)
            topos = (
                pd.DataFrame(topos.values.reshape(-1, N), columns=col_labels)
                .dropna()
                .astype(int)
            )
            output = {k: topos[k].values for k in col_labels}

        # output
        if dtype == 'dict':
            return output
        elif dtype == 'df':
            try:
                df = pd.DataFrame(output)
            except ValueError:
                df = pd.Series(output)
            df.attrs.update({'section': section.name})
            return df
