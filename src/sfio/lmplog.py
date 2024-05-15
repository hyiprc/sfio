__all__ = ['Lmplog']

import copy

import numpy as np
import pandas as pd

from . import WARNING
from .base import ReadOnly

thermo_alias = {
    'tpcpu': 't/cpu',
    'spcpu': 's/cpu',
    'cpuremain': 'cpuleft',
    'timeremain': 'timeoutleft',
    'pe': 'poteng',
    'ke': 'kineng',
    'etotal': 'toteng',
    'evdwl': 'e_vdwl',
    'ecoul': 'e_coul',
    'epair': 'e_pair',
    'ebond': 'e_bond',
    'eangle': 'e_angle',
    'edihed': 'e_dihed',
    'eimp': 'e_impro',
    'emol': 'e_mol',
    'elong': 'e_long',
    'etail': 'e_tail',
    'vol': 'volume',
    'dihedrals': 'diheds',
    'impropers': 'impros',
}
ialias = {v: k for k, v in thermo_alias.items()}

inttyp = [
    'step',
    'elapsed',
    'elaplong',
    'part',
    'atoms',
    'bonds',
    'angles',
    'dihedrals',
    'impropers',
    'nbuild',
    'ndanger',
]

energy_keywords = [
    'pe',
    'ke',
    'etotal',
    'evdwl',
    'ecoul',
    'epair',
    'ebond',
    'eangle',
    'edihed',
    'eimp',
    'emol',
    'elong',
    'etail',
    'enthalpy',
]

unittyp = {
    'temp': 'temperature',
    'density': 'density',
    'vol': 'volume',
    **{_: 'angle' for _ in ['cellalpha', 'cellbeta', 'cellgamma']},
    **{_: 'time' for _ in ['dt', 'time', 'tpcpu']},
    **{_: 'force' for _ in ['fmax', 'fnorm']},
    **{
        _: 'pressure'
        for _ in ['press', 'pxx', 'pyy', 'pzz', 'pxy', 'pzy', 'pyz']
    },
    **{
        _: 'energy'
        for _ in energy_keywords
        + [
            'ecouple',
            'econserve',
        ]
    },
    **{
        _: 'distance'
        for _ in [
            'lx',
            'ly',
            'lz',
            'xlo',
            'xhi',
            'ylo',
            'yhi',
            'zlo',
            'zhi',
            'xlat',
            'ylat',
            'zlat',
            'cella',
            'cellb',
            'cellc',
        ]
    },
}

units_convert = {
    'real_to_metal': {
        'time': 1.0e-3,
        'energy': 0.0433634,
        'force': 0.0433634,
        'pressure': 1.01325,
    },
}

blank_output = {
    'dataline': '',
    'units': 'metal',
    '_key': [],
    **{k: 0 for k in ['_', 'n', 'Nrun', 'Nmin', 'Neq']},
    **{k: [] for k in ['ix_min', 'ix_eq', 'key']},
}


def update_data(output):
    if output['dataline'].strip() == '':
        return

    ln = output['dataline'].split()
    output['dataline'] = ''
    key = [k.lower() for k in ln[0::3]]

    to_metal = output['units'].endswith('_to_metal')

    def metal_unit(k, v):
        k = ialias.get(k, k)
        if to_metal and k in unittyp:
            u = output['units']
            v = v * units_convert[u].get(unittyp[k], 1.0)
        return v

    value = [
        int(v) if k in inttyp else metal_unit(k, float(v))
        for k, v in zip(key, ln[2::3])
    ]

    # record data
    outkey = []
    for k, v in zip(key, value):
        if k in outkey:
            continue
        if k not in output:
            if output['n'] > 0:
                output.update({k: [np.nan] * output['n']})
            else:
                output.update({k: []})
        output[k].append(v)
        outkey.append(k)
    output['n'] += 1

    # get key if not exist
    try:
        output['_key'][0]
    except Exception:
        # fill None to non-existing thermo keywords
        for k in output['key']:
            if k not in key:
                output[k].append(np.nan)
        # accumulate thermo keywords
        output['key'] += [s for s in outkey if s not in output['key']]
        # link alias keys
        for c in outkey:
            try:
                output[ialias[c]] = output[c]
            except Exception:
                continue

    # update min and eq index
    me = {-1: 'min', 1: 'eq'}[output['_']]
    output[f'ix_{me}'][-1][1] = output['n'] - 1
    if 'step' in output:
        output[f'N{me}'] = sum(
            [
                output['step'][n[1]] - output['step'][n[0]]
                if n and n[1] is not None
                else 0
                for n in output[f'ix_{me}']
            ]
        )


def parse_stream(self, line, to_metal=True):  # noqa: C901
    """
    Read data from lammps log file
    """
    line = line.rstrip().replace('\t', ' ')

    if line.startswith('LAMMPS '):
        self.data = copy.deepcopy(blank_output)

    elif line.startswith('units '):
        self.data['units'] = u = line.split()[1]
        if to_metal and u != 'metal':
            k = u + '_to_metal' * (u != 'metal')
            if k not in units_convert:
                WARNING(f'no conversion factor for {k} in units_convert')
            else:
                self.data['units'] = k

    elif line.startswith('minimize '):
        self.data['ix_min'].append([self.data['n'], None])
        self.data['_'] = -1
        return
    elif line.startswith('run '):
        try:
            self.data['Nrun'] += int(line.split()[1])
        except Exception:
            return
        self.data['ix_eq'].append([self.data['n'], None])
        self.data['_'] = 1
        return

    elif line.startswith('Per MPI rank memory allocation '):
        self.data['_'] *= 2
        self.data['_key'] = []
        return
    elif line.startswith('Loop time of '):
        update_data(self.data)
        self.data['_'] = 0
        return

    elif 'ERROR: ' in line:
        print(line.strip())

    if '_' not in self.data or self.data['_'] == 0:
        return

    # process header
    if ' Step ' in line and ' CPU ' in line:
        if abs(self.data['_']) == 2:
            # mark style to 'multi'
            self.data['_'] = int(0.5 * self.data['_'])
        update_data(self.data)
        ln = line.split(' Step ')[1].split(' CPU ')
        self.data[
            'dataline'
        ] = f"step = {ln[0].split()[0]} cpu = {ln[1].split()[1]}"
        return
    elif abs(self.data['_']) == 2:
        self.data['_key'] = [s.lower() for s in line.split()]
        self.data['key'] += [
            s for s in self.data['_key'] if s not in self.data['key']
        ]
        self.data['_'] = int(0.5 * self.data['_'])
        return

    ln = line.split()
    nk = len(self.data['_key'])

    # ----- thermo_modify line multi -----
    if (
        ' = ' in line
        and not line.startswith(' ')
        and all([s == '=' for s in ln[1::3]])
    ):
        self.data['dataline'] += ' ' + line
        dk = set([s.lower() for s in self.data['dataline'].split()[0::3]])
        if len(dk) != nk:
            return

    # ----- thermo_modify line one -----
    elif len(ln) == nk:
        try:
            [float(v) for v in ln]
            self.data['dataline'] += ' '.join(
                [f'{k} = {v}' for k, v in zip(self.data['_key'], ln)]
            )
        except Exception:
            return

    update_data(self.data)


class Lmplog(ReadOnly):
    """LAMMPS log file"""

    def scan(self):
        pass

    def parse(self, section, dtype='df'):
        self.data = copy.deepcopy(blank_output)

        for line in self:
            parse_stream(self, line.decode(), to_metal=False)

        outkeys = ['run_type'] + self.data['key']
        output = {k: self.data.get(k, []) for k in outkeys}

        # mark each step as minimization or equilibration
        output['run_type'] = [''] * self.data['n']
        for s in ['min', 'eq']:
            for i0, i1 in self.data[f'ix_{s}']:
                for i in range(i0, i1 + 1):
                    output['run_type'][i] = s

        # metadata
        metadata = {'units': self.data['units']}

        # output
        if dtype == 'dict':
            output.update(metadata)
            return output
        elif dtype == 'df':
            df = pd.DataFrame(output, columns=outkeys)
            df.attrs.update(metadata)
            return df
