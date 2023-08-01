__all__ = ['Atsk']

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import ERROR, logger
from .base import Fortran_unformatted, ReadOnly
from .box import Box


class Atsk(ReadOnly):
    """Atomsk binary format, temporary file use only"""

    def __init__(self, fpath):
        self.fpath = Path(fpath)
        logger.debug(f"file: {self.fpath}")
        self.f = f = Fortran_unformatted(self.fpath)

        # check file format
        identifier = '0.8 Atomsk binary file'
        m, b = f._get_block()
        if not f._to_str(m, b) == identifier.ljust(m):
            ERROR(f'not {Atsk.identifier}')

    # -----------------------------------------------

    def parse(self):
        """
        atomsk binary format
        (see atomsk repo: src/output/out_atsk.f90)
        """

        f = self.f
        to_str = f._to_str
        to_float = f._to_float

        attrs = {}

        # (see output/writeout.f90)
        _, (Nxyz, Nshell, Naux, Nauxname, Ncomment) = f._get_block()
        logger.debug(f"{Nxyz:9d} coordinates")
        logger.debug(
            f"{Nshell:9d} ionic shells (positions for core/shell model)"
        )
        logger.debug(
            "\n{Nauxname:9d} auxilary properties (velocity, forces, etc.)\n"
        )
        logger.debug(f"{Naux:9d} entries in each property")
        logger.debug(f"{Ncomment:9d} comments")

        cell = np.round(to_float(64, f._get_block()[1]).reshape(3, 3).T, 6)
        attrs['box'] = box = Box()
        box.set_input(cell, typ='basis')
        logger.debug(f"\ncell vectors:\n{box.output['v']}")

        xyza = to_float(64, f._get_block()[1]).reshape(4, -1).T
        df = pd.DataFrame(
            xyza, columns=['x', 'y', 'z', 'atomic_number']
        ).astype({'atomic_number': 'uint32'})
        logger.debug("\ncoordinates, atomic number:")
        logger.debug(df)

        if Nshell > 0:
            shell = to_float(64, f._get_block()[1]).reshape(4, -1).T
            attrs['ionic_shells'] = pd.DataFrame(
                shell, columns=['position', 'number1', 'number2', 'number3']
            )
            logger.debug("ionic shell position, number:")
            logger.debug(attrs['ionic_shells'])

        if Naux > 0:
            prop_name = to_str(*f._get_block()).split()
            prop = to_float(64, f._get_block()[1]).reshape(Nauxname, -1).T
            attrs['properties'] = pd.DataFrame(prop, columns=prop_name)
            logger.debug(f"\nproperties:\n{attrs['properties']}")

        if Ncomment > 0:
            m, b = f._get_block()
            temp = to_str(m, b).rstrip()
            attrs['comments'] = temp
            logger.debug(f"\ncomments:\n{temp}")

        df.attrs.update(attrs)

        return df

    # -----------------------------------------------


if __name__ == '__main__':
    df = Atsk.read(sys.argv[1])
    print(df)
    print(df.attrs)
