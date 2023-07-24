rootname = "fio"

import inspect
from pathlib import Path


def abspath(path):
    return Path(path).expanduser().resolve().absolute()


rootdir = abspath(inspect.getfile(__import__(rootname))).parent

with open(rootdir / 'VERSION') as f:
    __version__ = str(f.readline()).strip()
