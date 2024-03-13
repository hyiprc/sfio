_all__ = ['Pdb']

import numpy as np
import pandas as pd

from .base import ReadOnly, Sectioned
from .box import Box

section_name = {
    b'HEADER': 'header',
    b'OBSLTE': 'header',
    b'TITLE': 'header',
    b'SPLIT': 'header',
    b'CAVEAT': 'header',
    b'COMPND': 'header',
    b'SOURCE': 'header',
    b'KEYWDS': 'header',
    b'EXPDTA': 'header',
    b'NUMMDL': 'header',
    b'MDLTYP': 'header',
    b'AUTHOR': 'header',
    b'REVDAT': 'header',
    b'SPRSDE': 'header',
    b'JRNL': 'header',
    b'REMARK': 'header',
    b'CRYST1': 'box',
    b'ORIGX1': 'box',
    b'ORIGX2': 'box',
    b'ORIGX3': 'box',
    b'SCALE1': 'box',
    b'SCALE2': 'box',
    b'SCALE3': 'box',
    b'MTRTX1': 'box',
    b'MTRTX2': 'box',
    b'MTRTX3': 'box',
    b'MODEL': 'atoms',
    b'ATOM': 'atoms',
    b'ANISOU': 'atoms',
    b'TER': 'atoms',
    b'HETATM': 'atoms',
    b'ENDMDL': 'atoms',
    b'CONECT': 'bonds',
}


class Pdb(ReadOnly, Sectioned):
    """Protein Data Bank Files"""

    def scan(self):
        with self.open() as fd:
            fd.seek(self.scanned)  # resume from last read

            for line in fd:
                record = line.split(None, 1)[0]
                sect = section_name.get(record, None)

                if sect not in self.sections:
                    for k in self.sections:
                        self.end_section(k)
                    self.start_section(sect)
                    self.scanned = fd.tell()
                    continue

                self.scanned = fd.tell()

        self.sections['file'] = [0]

    def parse(self, section, dtype='dict'):
        output = None

        if section.name == 'file':
            return {
                k: getattr(section.section(k), dtype)
                for k in ['box', 'atoms', 'bonds']
            }

        elif section.name == 'box':
            box = Box()
            for line in section.f:
                if line.startswith(b'CRYST1'):
                    box_input = b' '.join(
                        [
                            line[7:16],  # a
                            line[16:25],  # b
                            line[25:34],  # c
                            line[34:41],  # alpha
                            line[41:48],  # beta
                            line[48:55],  # gamma
                            # line[56:67],  # space_group
                            # int(line[67:71]),  # 'Z'
                        ]
                    ).decode()
                    box.set_input(box_input, typ='lattice')
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
            col_labels = [
                'record',
                'id',
                'name',
                'altloc',
                'resname',
                'chain',
                'resid',
                'insertion',
                'x',
                'y',
                'z',
                'occupancy',
                'beta',
                'custom',
                'segname',
                'element',
                'charge',
            ]
            atoms = pd.read_fwf(
                section.f,
                widths=[6, 6, 4, 1, 4, 1, 4, 4, 8, 8, 8, 6, 6, 6, 4, 2, 2],
                names=col_labels,
                dtype_backend='pyarrow',
            )
            output = {k: atoms[k].values for k in col_labels}

        elif section.name == 'bonds':
            b = np.genfromtxt(
                section.f,
                delimiter=[6, 5, 5, 5, 5, 5],
                filling_values=-1,
                usecols=(1, 2, 3, 4, 5),
                dtype=int,
            )
            b = np.c_[
                b[:, 0],
                b[:, 1],
                b[:, 0],
                b[:, 2],
                b[:, 0],
                b[:, 3],
                b[:, 0],
                b[:, 4],
            ].reshape(-1, 2)
            bonds = np.unique(b[(b[:, 0] < b[:, 1]), :], axis=0)
            output = {'atom-1': bonds[:, 0], 'atom-2': bonds[:, 1]}

        # output
        if dtype == 'dict':
            return output
        elif dtype == 'df':
            try:
                return pd.DataFrame(output)
            except ValueError:
                return pd.Series(output)
