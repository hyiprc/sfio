available = {
    # 'name': ('module','class','mode'),
    'lmpdata': ('lmpdata', 'Lmpdata', 'rw'),  # LAMMPS data file
    'lmpdump': ('lmpdump', 'Lmpdump', 'rw'),  # LAMMPS dump file
    'lmplog': ('lmplog', 'Lmplog', 'ro'),  # LAMMPS log file
    '.lmp': ('lmpdata', 'Lmpdata', 'ro'),  # LAMMPS data file
    '.data': ('lmpdata', 'Lmpdata', 'ro'),  # LAMMPS data file
    '.dump': ('lmpdump', 'Lmpdump', 'rw'),  # LAMMPS dump file
    '.atsk': ('atsk', 'Atsk', 'ro'),  # Atomsk temporary file
    '.psf': ('psf', 'Psf', 'ro'),  # X-PLOR Protein Structure file
    '.pdb': ('pdb', 'Pdb', 'ro'),  # Protein Data Bank file
    '.json': ('_json', 'Json', 'rw'),  # JavaScript Object Notation
    '.yaml': ('yaml', 'Yaml', 'rw'),  # YAML Ain’t Markup Language
    '.yml': ('yaml', 'Yaml', 'rw'),  # YAML Ain’t Markup Language
}
