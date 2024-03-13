__all__ = ['Lmpdata']

import pandas as pd

from . import func, logger
from .base import ReadOnly, Sectioned
from .box import Box


class Lmpdata(ReadOnly, Sectioned):
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

    @property
    def style(self):
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
            atoms.sort_index(inplace=True)
            output = {k: atoms[k].values for k in col_labels}

        elif section.name == 'velocities':
            col_labels = ['id', 'vx', 'vy', 'vz']
            velocities = pd.read_csv(
                section.f,
                sep=r'\s+',
                header=0,
                names=col_labels,
            )
            velocities.sort_index(inplace=True)
            output = {k: velocities[k].values for k in col_labels}

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
            topos.sort_index(inplace=True)
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
