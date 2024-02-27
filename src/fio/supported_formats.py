available = {
    # 'name': ('module','class','mode'),
    'lmpdata': ('lmpdata', 'Lmpdata', 'ro'),  # LAMMPS data file
    'lmpdump': ('lmpdump', 'Lmpdump', 'rw'),  # LAMMPS dump file
    'lmplog': ('lmplog', '', 'ro'),  # LAMMPS log file
    '.lmp': ('lmpdata', 'Lmpdata', 'ro'),  # LAMMPS data file
    '.data': ('lmpdata', 'Lmpdata', 'ro'),  # LAMMPS data file
    '.dump': ('lmpdump', 'Lmpdump', 'rw'),  # LAMMPS dump file
    '.atsk': ('atsk', 'Atsk', 'ro'),  # Atomsk temporary file
    '.psf': ('psf', 'Psf', 'ro'),
}
