__all__ = ['Box']

import re
import sys
from types import MappingProxyType

import numpy as np
import pyarrow as pa

from . import ERROR, logger


def normalize(a, order=2, axis=-1):
    """Normalize row-listed vectors of a"""
    l2 = np.atleast_1d(np.linalg.norm(a, order, axis))
    l2[l2 == 0] = 1.0
    return np.atleast_1d(np.squeeze(a / np.expand_dims(l2, axis)))


def cross(v, u):
    """Cross products of v and u (match row-by-row)"""
    return normalize(np.cross(v, u))


deg2rad = np.pi / 180.0
rad2deg = 180.0 / np.pi
abg = ('alpha', 'beta', 'gamma')  # angle between b c, a c, a b


class BoxInputDict(dict):
    """This is a non-mutable dict"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self

    def __setattr__(self, key, value):
        if key not in [*self.keys(), '__dict__']:
            raise KeyError(f"'{key}' is not a Box input parameter")
        else:
            super().__setattr__(key, value)
            self._check_allow_tilt(key, value)

    def __setitem__(self, key, value):
        if key not in self:
            raise KeyError(f"'{key}' is not a Box input parameter")
        else:
            super().__setitem__(key, value)
            self._check_allow_tilt(key, value)

    def update(self, *args, **kwargs):
        frozen = set(self.keys())
        super().update(*args, **kwargs)
        invalidkeys = set(self.keys()).difference(frozen)
        if invalidkeys:
            logger.warning(
                f"Ignored invalid Box input parameters: {invalidkeys}"
            )
            for k in invalidkeys:
                self.pop(k)

    def _check_allow_tilt(self, key, value):
        if key in abg and value != 90:
            self.__dict__['allow_tilt'] = True
        elif key == 'allow_tilt' and not self['allow_tilt']:
            if any([self[k] != 90 for k in abg]):
                logger.warning(f"Non-orthogonal box, keeping {key} = True")
                self.__dict__['allow_tilt'] = True


class Box:
    schema = pa.schema(
        [
            ('x0', pa.float32()),
            ('y0', pa.float32()),
            ('z0', pa.float32()),
            ('lx', pa.float32()),
            ('ly', pa.float32()),
            ('lz', pa.float32()),
            ('alpha', pa.float32()),
            ('beta', pa.float32()),
            ('gamma', pa.float32()),
            ('allow_tilt', pa.bool_()),
            ('bx', pa.string()),
            ('by', pa.string()),
            ('bz', pa.string()),
        ]
    )

    def __init__(self, inputdict: dict = {}):
        self.input = BoxInputDict(
            {
                'x0': 0.0,
                'y0': 0.0,
                'z0': 0.0,
                'lx': 1.0,
                'ly': 1.0,
                'lz': 1.0,
                'alpha': 90.0,
                'beta': 90.0,
                'gamma': 90.0,
                'allow_tilt': False,
                'bx': 'pp',
                'by': 'pp',
                'bz': 'pp',
            }
        )
        self.input.update(inputdict)

        self.alias = {
            'vmd': 'lattice',
            'poscar': 'basis',
            'vasp': 'basis',
        }

    def __repr__(self):
        return f"<Box object at {hex(id(self))}, {self.input}>"

    def __str__(self):
        return self.report()

    def __getitem__(self, key):
        return self.input.get(key, self.output[key])

    def __setitem__(self, key, value):
        self.input[key] = value

    # -----------------------------------------------

    @property
    def output(self):
        _ = self.input.copy()

        for s in 'xyz':
            _[f'{s}lo'] = _[f'{s}0']
            _[f'{s}hi'] = _[f'{s}0'] + _[f'l{s}']

        lx, ly, lz = _['lx'], _['ly'], _['lz']

        _['allow_tilt'] |= any([_[s] != 90 for s in abg])

        _['cos_alpha'] = ca = np.cos(_['alpha'] * deg2rad)
        _['cos_beta'] = cb = np.cos(_['beta'] * deg2rad)
        _['cos_gamma'] = cg = np.cos(_['gamma'] * deg2rad)

        _['a'] = lx
        _['b'] = b = ly / (1.0 - cg**2.0) ** 0.5
        _['c'] = c = (
            lz
            / (1 - cb**2.0 - (ca - cg * cb) ** 2.0 / (1 - cg**2.0)) ** 0.5
        )

        _['xy'] = xy = b * cg
        _['xz'] = xz = c * cb
        _['yz'] = yz = (b * c * ca - xy * xz) / ly

        _['v'] = np.array(
            [
                [lx, 0.0, 0.0],  # v_a
                [xy, ly, 0.0],  # v_b
                [xz, yz, lz],  # v_c
            ]
        )

        # useful for coordinate transform
        _['u'] = normalize(_['v'])
        # useful for undo coordinate transform
        _['u_inv'] = np.linalg.inv(_['u'])

        # face normal, useful for cartesian to crystal fractional
        _['bn'] = np.r_[
            cross(_['u'][1], _['u'][2]),
            cross(_['u'][2], _['u'][0]),
            cross(_['u'][0], _['u'][1]),
        ].reshape(-1, 3)

        # get rid of small zero
        p = 9  # number < 1E-p is 0
        for s in _:
            try:
                _[s] = np.round(_[s], p)
            except Exception:
                continue

        return MappingProxyType(_)

    # -----------------------------------------------

    def _format_input(self, argv: str):
        if isinstance(argv, str):
            argv = re.split(r'\s*,\s*|\s+', argv.strip().replace('\n', ''))
        # check input length
        if len(argv) == 1:
            ERROR("Read Box from file is not yet implemented")  # TODO
        else:
            return np.array(argv, dtype=float)

    def _guess_type(self, argv):
        if argv is None:
            raise ERROR('Missing Box input parameters', trace=0)
        elif len(argv) == 9:
            if argv[0] < argv[1] and argv[2] < argv[3] and argv[4] < argv[5]:
                return 'lmpdata'
            elif argv[0] < argv[1] and argv[3] < argv[4] and argv[6] < argv[7]:
                return 'lmpdump'
            else:
                return 'basis'
        elif len(argv) == 6:
            if argv[1] <= 1 and argv[3] <= 1 and argv[4] <= 1:
                return 'dcd'
            else:
                return 'lattice'
        else:
            raise ERROR('Incorrect Box input parameters', trace=0)

    def set_input(self, argv, typ=None):
        data = self._format_input(argv)
        # detect type
        typ = self.alias.get(typ, typ)
        if typ is None:
            typ = self._guess_type(data)
        # handle specific box type
        _ = self.input
        func = getattr(self, f'_input_{typ}')
        _.update(func(data))
        # always allow tilt if not orthogonal
        if any([_[s] != 90 for s in abg]):
            _['allow_tilt'] = True
        return typ

    def _input_basis(self, v: np.ndarray):
        """Basis Vectors:
        | v_a[0], v_a[1], v_a[2] |
        | v_b[0], v_b[1], v_b[2] |
        | v_c[0], v_c[1], v_c[2] |
        """
        v = np.array(v).reshape(3, 3)
        u = normalize(v)
        return {
            'lx': v[0, 0],
            'ly': v[1, 1],
            'lz': v[2, 2],
            'alpha': np.arccos(np.dot(u[1], u[2])) * rad2deg,
            'beta': np.arccos(np.dot(u[0], u[2])) * rad2deg,
            'gamma': np.arccos(np.dot(u[0], u[1])) * rad2deg,
        }

    def _input_lmpdata(self, v: np.ndarray):
        """LMPDATA: xlo, xhi, ylo, yhi, zlo, zhi, xy, xz, yz"""
        xlo, xhi, ylo, yhi, zlo, zhi, xy, xz, yz = v
        return {
            'x0': xlo,
            'y0': ylo,
            'z0': zlo,
            # fmt: off
            **self._input_basis([
                [xhi - xlo,          0,          0],  # noqa: E201, E241
                [       xy,  yhi - ylo,          0],  # noqa: E201, E241
                [       xz,         yz,  zhi - zlo],  # noqa: E201, E241
            ]),
            # fmt: on
        }

    def _input_lmpdump(self, v: np.ndarray):
        """LMPDUMP: xlo, xhi, xy, ylo, yhi, xz, zlo, zhi, yz"""
        return self._input_lmpdata(np.take(v, [0, 1, 3, 4, 6, 7, 2, 5, 8]))

    def _input_dcd(self, v: np.ndarray):
        """DCD: a, cos_gamma, b, cos_beta, cos_alpha, c"""
        a, cg, b, cb, ca, c = v
        ly = b * (1 - cg**2.0) ** 0.5
        lz = c * (1 - cb**2 - (ca - cg * cb) ** 2 / (1 - cg**2.0)) ** 0.5
        return {
            'lx': a,
            'ly': ly,
            'lz': lz,
            'alpha': np.arccos(ca) * rad2deg,
            'beta': np.arccos(cb) * rad2deg,
            'gamma': np.arccos(cg) * rad2deg,
        }

    def _input_lattice(self, v: np.ndarray):
        """Lattice Parameters: a, b, c, alpha, beta, gamma"""
        a, b, c, alpha, beta, gamma = v
        ca = np.cos(alpha * deg2rad)
        cb = np.cos(beta * deg2rad)
        cg = np.cos(gamma * deg2rad)
        return self._input_dcd([a, cg, b, cb, ca, c])

    # -----------------------------------------------

    def report(self, typ='all'):
        _ = self.output

        v = _['v']
        fmt_basis = (
            f" {v[0, 0]:15.9f}  {v[0, 1]:15.9f}  {v[0, 2]:15.9f}\n"
            f" {v[1, 0]:15.9f}  {v[1, 1]:15.9f}  {v[1, 2]:15.9f}\n"
            f" {v[2, 0]:15.9f}  {v[2, 1]:15.9f}  {v[2, 2]:15.9f}"
        )

        fmt_lattice = f"{_['a']:g} {_['b']:g} {_['c']:g} {_['alpha']:g} {_['beta']:g} {_['gamma']:g}  a b c alpha beta gamma"

        fmt_lmpdata = (
            f" {_['xlo']:.7f} {_['xhi']:.7f}  xlo xhi\n"
            + f" {_['ylo']:.7f} {_['yhi']:.7f}  ylo yhi\n"
            + f" {_['zlo']:.7f} {_['zhi']:.7f}  zlo zhi"
            + f"\n {_['xy']:.7f} {_['xz']:.7f} {_['yz']:.7f}  xy xz yz"
        )

        fmt_lmpdump = (
            f"ITEM: BOX BOUNDS xy xz yz {_['bx']} {_['by']} {_['bz']}\n"
            f"{_['xlo']:.7f} {_['xhi']:.7f} {_['xy']:.7f}  xlo xhi xy\n"
            + f"{_['ylo']:.7f} {_['yhi']:.7f} {_['xz']:.7f}  ylo yhi xz\n"
            + f"{_['zlo']:.7f} {_['zhi']:.7f} {_['yz']:.7f}  zlo zhi yz"
        )

        fmt_dcd = f"{_['a']:g} {_['cos_gamma']:g} {_['b']:g} {_['cos_beta']:g} {_['cos_alpha']:g} {_['c']:g}  a cos_gamma b cos_beta cos_alpha c"

        typ = self.alias.get(typ, typ)
        if typ in ('basis', 'vasp', 'poscar'):
            return fmt_basis
        elif typ in ('lattice', 'vmd'):
            return fmt_lattice
        elif typ == 'lmpdata':
            return fmt_lmpdata
        elif typ == 'lmpdump':
            return fmt_lmpdump
        elif typ == 'dcd':
            return fmt_dcd
        else:
            return (
                "\n# ----- input parameters (origin, bb-length, angle, boundary) -----\n"
                f"{self.input}\n"
                "\n# ----- basis Vectors -----\n"
                f"{fmt_basis}\n"
                "\n# ----- lattice Parameters -----\n"
                f"{fmt_lattice}\n"
                "# alpha is between b c, beta a c, gamma a b\n"
                "\n# ----- lammps data file -----\n"
                f"{fmt_lmpdata}\n"
                "\n# ----- lammps dump file -----\n"
                f"{fmt_lmpdump}\n"
                "\n# ----- dcd file ----\n"
                f"{fmt_dcd}\n"
            )


if __name__ == '__main__':
    argv = ' '.join(sys.argv[1:])
    box = Box()
    typ = box.set_input(argv)
    print(f'input ({typ}): {argv}\n{box}')
