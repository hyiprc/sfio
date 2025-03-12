__all__ = ['Lmpdata']

import os
from textwrap import indent

import numpy as np
import pandas as pd

from . import WARNING, func, logger, rootdir, timefmt, timestamp
from .base import ReadWrite, Sectioned
from .box import Box


class Lmpdata(ReadWrite, Sectioned):
    """LAMMPS data file, see bottom of this file for file formats"""

    file_sections = [
        # required, section_name, start, end
        (1, 'header', None),
        (1, 'box', b' xlo xhi'),
        (0, 'masses', b'Masses'),
        (0, 'coeffs', b'Coeffs'),
        (1, 'atoms', b'Atoms'),
        (0, 'velocities', b'Velocities'),
        (0, 'bonds', b'Bonds'),
        (0, 'angles', b'Angles'),
        (0, 'dihedrals', b'Dihedrals'),
        (0, 'impropers', b'Impropers'),
    ]

    sect_basic = ['header', 'masses', 'atoms', 'velocities']
    sect_topo = ['bonds', 'angles', 'dihedrals', 'impropers']

    df_atoms_addsects = ['velocities']

    @property
    def style(self):
        try:
            return self._style
        except AttributeError:
            line = next(self.section('atoms').f).strip()
            self.style = line.decode().split('# ')[:2][-1]
            return self._style

    @style.setter
    def style(self, style):
        # define included sections
        atom_styles = {
            **{
                k: self.sect_basic + self.sect_topo
                for k in [
                    'atomic',
                    'full',
                    'molecular',
                    'charge',
                    'dipole',
                    'sphere',
                    'ellipsoid',
                ]
            },
            **{
                k[:-1]: self.sect_basic + self.sect_topo[:i]
                for i, k in enumerate(self.sect_topo[:3], 1)
            },
        }

        # TODO: auto detect style
        while style not in atom_styles:
            if hasattr(self, '_style'):
                style = self._style['name']
                break
            logger.warning(
                f'no style defined, choose from {list(atom_styles.keys())}'
            )
            style = input('lmpdata style = ')

        def insert(alist, item, pos):
            return alist[:pos] + item + alist[pos:]

        # define atom columns
        cols_atomic = ['id', 'type', 'x', 'y', 'z']
        cols_molecular = insert(cols_atomic, ['mol'], 1)
        cols_charge = insert(cols_atomic, ['q'], 2)
        atom_columns = {
            'atomic': cols_atomic,
            'full': insert(cols_molecular, ['q'], 3),
            'charge': cols_charge,
            'dipole': cols_charge + ['mux', 'muy', 'muz'],
            'sphere': insert(cols_atomic, ['diameter'], 2),
            'ellipsoid': insert(cols_atomic, ['ellipsoidflag', 'density'], 2),
            **{
                k: cols_molecular
                for k in ['molecular', 'angle', 'bond', 'dihedral']
            },
        }

        # define atom column output/input formats
        wfmt = {
            'id': '%d',
            'type': '%d',
            'mol': '%d',
            'q': '%.6f',
            'x': '%.6f',
            'y': '%.6f',
            'z': '%.6f',
            'mux': '%.6f',
            'muy': '%.6f',
            'muz': '%.6f',
            'diameter': '%f',
            'density': '%f',
            'ellipsoidflag': '%d',
            'volume': '%f',
        }
        map_fmt = {'d': int, 'f': float, 's': str}
        rfmt = {k: map_fmt[wfmt[k][-1]] for k in wfmt}

        # record style info
        self._style = {
            'name': style,
            'sections': atom_styles[style],
            'atoms_cols': atom_columns[style],
            'atoms_rfmt': {k: rfmt[k] for k in atom_columns[style]},
            'atoms_wfmt': {k: wfmt[k] for k in atom_columns[style]},
        }

    def scan_byline(self):
        with self.open() as fd:
            fd.seek(self.scanned)  # resume from last read

            if not self.scanned:
                self.start_section('header')

            file_sections = self.file_sections.copy()

            for line in fd:
                for i, (req, sect, pattern) in enumerate(file_sections[1:]):
                    if pattern is not None and pattern in line:
                        for _, prev_sect, _ in file_sections[: i + 1]:
                            self.end_section(prev_sect)
                            file_sections.pop(0)
                        self.start_section(sect)
                        break
                    if req and sect not in self.sections:
                        break

                self.scanned = fd.tell()

    def scan_bychunk(self):
        with self.open() as fd:
            fd.seek(self.scanned)  # resume from last read

            if not self.scanned:
                self.start_section('header')

            # search patterns up to a required section
            _, sects, starts = zip(*self.file_sections)
            patterns = list(dict.fromkeys(starts))
            bytelocs = func.search_in_file(fd, patterns, self.scanned)
            scanned = fd.tell()

            # lookup tables
            matches = dict(zip(patterns, bytelocs))

            # mark start and end of the sections
            for i, (req, sect, start) in enumerate(self.file_sections):
                if start is None:
                    continue
                for b0 in matches[start]:
                    self.scanned = b0
                    for _, prev_sect, _ in self.file_sections[: i + 1]:
                        self.end_section(prev_sect)
                    self.start_section(sect)
            self.scanned = scanned

    def scan(self, method='chunk'):
        logger.debug(f"Scan {self.type} file using '{method}' method.")
        return getattr(self, f"scan_by{method}")()

    def parse(self, section, dtype='dict'):
        def loop_lines(f, skip=0):
            """strip comments and skip empty lines"""
            comment = b''
            skipped = 0
            for line in f:
                ix = line.find(b'#')
                if ix >= 0:
                    line, comment = line[:ix], line[ix + 1 :].strip()
                line = line.strip()
                if line:
                    if skipped >= skip:
                        yield line.decode(), comment.decode()
                    else:
                        skipped += 1

        if section.name == 'header':
            output = {}
            for line, _ in loop_lines(section.f):
                v, k = line.split(None, 1)
                k = f"num_{k.replace(' ', '_')}"
                output[k] = int(v)

        elif section.name == 'box':
            box = Box()
            lines = [line for line, _ in loop_lines(section.f)]
            box['allow_tilt'] = len(lines) > 3
            lines.append(' 0.0 0.0 0.0' * (not box['allow_tilt']))
            box_input = ' '.join(
                [f"{line.split(s,1)[0]}" for line, s in zip(lines, 'xyzx')]
            )
            box.set_input(box_input, typ='lmpdata')
            # output
            if dtype == 'obj':
                return box
            output = {**box.input}

        elif section.name == 'masses':
            col_labels = ['id', 'mass']
            output = {'id': [], 'mass': [], 'label': []}
            for line, label in loop_lines(section.f, skip=1):
                ID, mass = line.split()
                output['id'].append(ID)
                output['mass'].append(round(float(mass), 6))
                output['label'].append(label)

        elif section.name == 'atoms':
            # get column labels
            _, self.style = next(loop_lines(section.f))
            col_labels = self.style['atoms_cols']
            # read atoms and create dataframe
            atoms = pd.read_csv(
                section.f,
                sep=r'\s+',
                header=0,
                names=col_labels,
            )
            atoms.sort_values(by='id', inplace=True)
            output = {k: atoms[k].values for k in col_labels}

        elif section.name == 'velocities':
            col_labels = ['id', 'vx', 'vy', 'vz']
            vels = pd.read_csv(
                section.f,
                sep=r'\s+',
                header=0,
                names=col_labels,
            )
            vels.sort_values(by='id', inplace=True)
            output = {k: vels[k].values for k in col_labels}

        elif section.name in self.sect_topo:
            # get column labels
            N = min(self.sect_topo.index(section.name) + 2, 4)
            col_labels = ['id', 'type'] + [f'atom-{i+1}' for i in range(N)]
            # read bonds/angles/dihedrals/impropers and create dataframe
            topos = pd.read_csv(
                section.f,
                sep=r'\s+',
                header=0,
                names=col_labels,
            )
            topos.sort_values(by='id', inplace=True)
            output = {k: topos[k].values for k in col_labels}

        # output
        if dtype == 'dict':
            return output
        elif dtype == 'df':
            try:
                df = pd.DataFrame(output)
            except ValueError:
                df = pd.Series(output)
            if section.name == 'atoms':
                df.attrs.update({'style': self.style['name']})
            return df

    @classmethod
    def write(
        cls,
        fpath,
        df,
        style=None,
        overwrite=False,
        header='',
        dated=True,
        **kwargs,
    ):
        if style is None:
            default = 'full' if 'q' in df.columns else 'atomic'
            style = df.attrs.get('style', default)

        # new file
        self = cls(fpath, mode='wb')
        self.style = style
        logger.info(f"Write Lammps data file {fpath}, style='{style}'")

        # for df.to_csv, output array values as text
        fmt_arrayonly = {
            'sep': ' ',
            'mode': 'ab',
            'header': False,
            'index': False,
            'na_rep': 'nan',
            'float_format': '%.6f',
        }

        if 'id' not in df:
            df['id'] = df.index + 1

        # TODO: establish a minimal atoms df based on this, similar to box.input
        if 'atomic_number' in df:
            uniq = np.sort(np.unique(df['atomic_number']))

            if 'type' not in df:
                to_type = {int(a): t for t, a in enumerate(uniq, 1)}
                df['type'] = df['atomic_number'].map(to_type)

            if 'masses' not in df.attrs:
                ptable = pd.read_parquet(rootdir / 'data/ptable.parquet')
                df.attrs['masses'] = {
                    'id': list(range(1, len(uniq) + 1)),
                    'mass': [ptable['atomic_mass'][ID - 1] for ID in uniq],
                    'label': [ptable['symbol'][ID - 1] for ID in uniq],
                }

        # ...............................................
        f = self.open()

        # header
        date = f"{timefmt(timestamp())}\n" * dated
        header = f"LAMMPS data file.\n{date}{header}"
        f.write(indent(header, '# ', lambda line: True).encode())
        f.write(b'\n')

        # count atoms, bonds, angles, dihedrals, impropers
        sect_topo = [s for s in cls.sect_topo if s in df.attrs]
        sections = ['atoms', *sect_topo]

        for sect in sections:
            _df = df.attrs.get(sect, df)
            count = _df['id'].shape[0]
            line = f"{count} {sect}"
            logger.info(line)
            f.write(f" {line}\n".encode())

        for sect in sections:
            _df = df.attrs.get(sect, df)
            count = pd.unique(_df['type']).size
            # compare count with number from header
            header = _df.attrs.get('header', {})
            count0 = header.get(f"num_{sect[:-1]}_types", -1)
            if count != count0:
                logger.warning(
                    f"actual number of {sect[:-1]} types ({count}) does "
                    f"not match header ({count0}), will use the larger number"
                )
            line = f"{max(count, count0)} {sect[:-1]} types"
            logger.info(line)
            f.write(f" {line}\n".encode())

        # box
        box = Box(df.attrs['box'])
        logger.info(f"writing box: {box.input}")
        _ = box.output
        ortho = '#' * (_['xy'] + _['xz'] + _['yz'] == 0)
        ortho = kwargs.get('ortho', ortho)
        f.write(
            (
                f" {_['xlo']:.7f} {_['xhi']:.7f}  xlo xhi\n"
                f" {_['ylo']:.7f} {_['yhi']:.7f}  ylo yhi\n"
                f" {_['zlo']:.7f} {_['zhi']:.7f}  zlo zhi\n"
                f"{ortho} {_['xy']:.7f} {_['xz']:.7f} {_['yz']:.7f}  xy xz yz\n"
            ).encode()
        )

        # masses
        masses = pd.DataFrame(df.attrs['masses'])
        logger.info(f"writing masses: {list(masses.columns)}")
        fmt_masses = {'mass': '{:.6g}', 'label': ' # {}'}
        f.write(b"\n Masses\n\n")
        f.write(
            masses.style.format(fmt_masses, na_rep='null')
            .hide(axis='columns')
            .hide(axis='index')
            .to_string()
            .encode()
        )

        # atoms
        atom_cols = self.style['atoms_cols']
        missing = [c for c in atom_cols if c not in df.columns]
        if missing:
            WARNING(f"missing columns in 'atoms' section: {missing}")
        empty = pd.DataFrame(columns=missing)
        atoms = pd.concat((df, empty), axis=1)[atom_cols]
        logger.info(f"writing atoms: {list(atoms.columns)}")
        f.write(f"\n Atoms  # {self.style['name']}\n\n".encode())
        atoms.to_csv(f, **fmt_arrayonly)

        # bonds, angles, dihedrals, impropers
        for sect in sect_topo:
            f.write(f"\n {sect.capitalize()}\n\n".encode())
            topo = pd.DataFrame(df.attrs[sect])
            logger.info(f"writing {sect}: {list(topo.columns)}")
            topo.to_csv(f, **fmt_arrayonly)

        # velocities
        vel_cols = [s for s in ['vx', 'vy', 'vz'] if s in df.columns]
        if vel_cols:
            vels = df[['id', *vel_cols]]
            logger.info(f"writing velocities: {list(vels.columns)}")
            f.write("\n Velocities\n\n".encode())
            vels.to_csv(f, **fmt_arrayonly)

        f.close()
        # ...............................................

        return os.stat(fpath).st_size


"""
http://www.smcm.iqfr.csic.es/docs/lammps/atom_style.html
angle   bonds and angles    bead-spring polymers with stiffness
atomic  only the default values coarse-grain liquids, solids, metals
bond    bonds   bead-spring polymers
charge  charge  atomic system with charges
dipole  charge and dipole moment    system with dipolar particles
electron    charge and spin and eradius electronic force field
ellipsoid   shape, quaternion for particle orientation, angular momentum   extended aspherical particles
full    molecular + charge  bio-molecules
line    end points, angular velocity    rigid bodies
meso    rho, e, cv  SPH particles
molecular   bonds, angles, dihedrals, impropers uncharged molecules
peri    mass, volume    mesocopic Peridynamic models
sphere  diameter, mass, angular velocity    granular models
tri corner points, angular momentum rigid bodies
wavepacket  charge, spin, eradius, etag, cs_re, cs_im   AWPMD

http://www.smcm.iqfr.csic.es/docs/lammps/read_data.html
angle   atom-ID molecule-ID atom-type x y z
atomic  atom-ID atom-type x y z
bond    atom-ID molecule-ID atom-type x y z
charge  atom-ID atom-type q x y z
dipole  atom-ID atom-type q x y z mux muy muz
electron    atom-ID atom-type q spin eradius x y z
ellipsoid   atom-ID atom-type ellipsoidflag density x y z
full    atom-ID molecule-ID atom-type q x y z
line    atom-ID molecule-ID atom-type lineflag density x y z
meso    atom-ID atom-type rho e cv x y z
molecular   atom-ID molecule-ID atom-type x y z
peri    atom-ID atom-type volume density x y z
sphere  atom-ID atom-type diameter density x y z
tri atom-ID molecule-ID atom-type triangleflag density x y z
wavepacket  atom-ID atom-type charge spin eradius etag cs_re cs_im x y z
hybrid  atom-ID atom-type x y z sub-style1 sub-style2 ...
"""
