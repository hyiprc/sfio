__all__ = ['Atsk']

import numpy as np
import pandas as pd

from . import ERROR
from .base import Fortran_unformatted as fort
from .base import ReadOnly, Sectioned
from .box import Box


class Atsk(ReadOnly, Sectioned):
    """Atomsk binary format, temporary file use only
    see atomsk repo:
        src/output/out_atsk.f90
        src/output/writeout.f90
    """

    identifier = '0.8 Atomsk binary file'
    dtype = 'int32'

    def scan(self, size: int = -1):
        with self.open() as fd:
            fd.seek(0)  # rewind the file

            # check file header
            self.start_section('header')
            m, b = fort.get_block(fd, self.dtype)
            if not fort.to_str(m, b) == self.identifier.ljust(m):
                ERROR(f'not {self.identifier}')
            _, N = fort.get_block(fd, self.dtype)
            self.scanned = fd.tell()
            self.end_section('header')

            # file sections
            for name, num_blocks, exist in [
                ('box', 1, True),
                ('atoms', 1, N[0]),
                ('ionic_shells', 1, N[1]),
                ('properties', 2, N[2]),
                ('comments', 1, N[4]),
            ]:
                if bool(exist):
                    self.start_section(name)
                    for _ in range(num_blocks):
                        fort.get_block(fd, self.dtype)
                    self.scanned = fd.tell()
                    if self.scanned >= size > 0:
                        return
                    self.end_section(name)

    def parse(self, section, dtype='dict'):
        with self.open() as fd:
            fd.seek(section.start_byte)
            m, b = fort.get_block(fd, self.dtype)

            if section.name == 'header':
                _, N = fort.get_block(fd, self.dtype)
                # output
                out = {
                    'identifier': fort.to_str(m, b).strip(),
                    'num_atoms': N[0],
                    'num_ionic_shells': N[1],
                    'num_property_entries': N[2],
                    'num_properties': N[3],
                    'num_comments': N[4],
                }
                if dtype == 'df':
                    return pd.Series(out)
                return out

            elif section.name == 'box':
                box_input = np.round(fort.to_float(64, b).reshape(3, 3).T, 6)
                box = Box()
                box.set_input(box_input, typ='basis')
                # output
                if dtype == 'obj':
                    return box
                out = {**box.input}
                if dtype == 'df':
                    return pd.Series(out)
                return out

            elif section.name == 'atoms':
                atoms = fort.to_float(64, b).reshape(4, -1).T
                # output
                out = {
                    'x': atoms[:, 0],
                    'y': atoms[:, 1],
                    'z': atoms[:, 2],
                    'atomic_number': atoms[:, 3].astype(np.int8),
                }
                if dtype == 'df':
                    return pd.DataFrame(out)
                return out

            elif section.name == 'ionic_shells':
                # positions for core/shell model
                shells = fort.to_float(64, b).reshape(4, -1).T
                # output
                out = {
                    'position': shells[:, 0],
                    'number1': shells[:, 1],
                    'number2': shells[:, 2],
                    'number3': shells[:, 3],
                }
                if dtype == 'df':
                    return pd.DataFrame(out)
                return out

            elif section.name == 'properties':
                # auxilary properties (velocity, forces, etc.)
                props = fort.to_str(m, b).split()
                P = fort.to_float(64, fort.get_block(fd, self.dtype)[1])
                values = P.reshape(len(props), -1).T
                # output
                out = {prop: values[:, i] for i, prop in enumerate(props)}
                if dtype == 'df':
                    return pd.DataFrame(out)
                return out

            elif section.name == 'comments':
                # output
                return {'comments': fort.to_str(m, b).rstrip()}
