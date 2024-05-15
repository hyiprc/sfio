__all__ = [
    'ReadOnly',
    'ReadWrite',
    'Sectioned',
    'MultiFrames',
    'Fortran_unformatted',
    'File',
    'Section',
]

import abc
import gzip
import io
from pathlib import Path

import numpy as np

from . import ERROR, logger


class File(abc.ABC):
    allow_cache = True

    def __init__(self, name, **kwargs):
        self.scanned = 0  # number of bytes already scanned
        self.sections = {}  # sections and byte positions
        self.name = name
        self.kwargs = kwargs
        self.type = self.__class__.__name__
        # handle compressed file
        if not isinstance(name, int) and Path(name).suffix == ".gz":
            self.opener = gzip.open
        else:
            self.opener = io.FileIO

    @property
    def cache(self):
        return {k: getattr(self, k) for k in ['scanned', 'sections']}

    def __repr__(self):
        try:
            Nfr = f", {len(self)} frames"
        except TypeError:
            Nfr = ""
        sect = list(self.sections.keys())
        sections = f". File.sections = {sect}." if sect else ""
        return f"<{self.type} File at {hex(id(self))}{Nfr}>{sections}"

    def __iter__(self):
        with self.open() as f:
            for line in f:
                yield line

    def open(self):
        """open file, no buffering"""
        return self.opener(self.name, **self.kwargs)

    @abc.abstractmethod
    def scan(self):
        # quick scan a file (lazy loading)
        pass

    @abc.abstractmethod
    def parse(self, section, dtype='dict'):
        # parse section of a file
        pass

    def __getattr__(self, dtype):
        if 'file' in self.sections:
            return self.parse(self.section('file'), dtype)
        ERROR(f"File has no attribute '{dtype}'. {self}", AttributeError)


class ReadOnly(File):
    @classmethod
    def write(cls, *args, **kwargs):
        ERROR(f"{cls.__name__} file format is ReadOnly", NotImplementedError)


class ReadWrite(File):
    @classmethod
    @abc.abstractmethod
    def write(cls, fpath, data, **kwargs):
        pass


# -----------------------------------------------


class Section:
    """section of a file, can be casted to different data types"""

    def __init__(
        self,
        _File: File,
        start_byte: int = 0,
        num_bytes=float('inf'),
        name: str = 'file',
    ):
        self.file = _File
        max_byte = _File.open().seek(0, 2)
        self.start_byte = Sectioned.get_index(start_byte, max_byte)
        max_num_bytes = max(0, max_byte - self.start_byte)
        self.num_bytes = int(max(0, min(num_bytes, max_num_bytes)))
        self.name = str(name)

    def __repr__(self):
        start, N = self.start_byte, self.num_bytes
        is_slice = start != 0 or N != self.file.scanned
        filetype = self.file.__class__.__name__
        section = f" {self.__class__.__name__} '{self.name}'," * is_slice
        byteinfo = f" seek {start} read {N} bytes" * is_slice
        return f"<{filetype}{section} File at {hex(id(self.file))}{byteinfo}>"

    def section(self, name, instance: int = None):
        """get sub-section"""
        a = self.start_byte
        b = a + self.num_bytes
        return Sectioned.get_section(self.file, name, a, b, instance)

    @property
    def raw(self):
        with self.file.open() as f:
            f.seek(self.start_byte)
            return f.read(self.num_bytes)

    @property
    def text(self):
        try:
            return self.raw.decode().rstrip()
        except UnicodeDecodeError:
            pass

    @property
    def f(self):
        return io.BytesIO(self.raw)

    def __iter__(self):
        for line in self.f:
            yield line

    def parse(self, dtype='dict'):
        return self.file.parse(self, dtype)

    def __getattr__(self, dtype):
        output = self.parse(dtype)
        if output is None:
            err_msg = f"cannot cast '{self.name}' section to '{dtype}'"
            ERROR(err_msg, AttributeError)
        return output


class Sections(list):
    def __init__(self, iterable):
        def validate(item):
            if isinstance(item, Section):
                return item
            ERROR(
                f"Section object expected, got {type(item).__name__}",
                TypeError,
            )

        super().__init__(validate(item) for item in iterable)

    def __getitem__(self, indexing):
        getitem = super().__getitem__
        # int or slice
        if isinstance(indexing, (int, slice)):
            out = getitem(indexing)
        # fancy indexing
        elif hasattr(indexing, '__iter__'):
            out = [getitem(i) for i in indexing]
        # entire range
        elif indexing is Ellipsis:
            out = self
        # unsupported indexing
        else:
            msg = 'indices must be integers, slices, ellipsis (`...`), or integer lists'
            ERROR(msg, TypeError)
        # for list with only one Section, return the Section
        if isinstance(out, (Section, Sections)):
            return out
        elif hasattr(out, '__len__') and len(out) == 1:
            return out[0]
        return Sections(out)


# -----------------------------------------------


class Sectioned(abc.ABC):
    """Provide functions to mark and locate section of a File."""

    def end_section(self, name: str):
        """Mark the end of a Section."""
        if name is None or self.scanned is None:
            return
        section = self.sections.get(name, [])
        if len(section) % 2 == 1 and self.scanned > section[-1]:
            section.append(self.scanned)

    def start_section(self, name: str):
        """Mark the beginning of a Section."""
        if name is None or self.scanned is None:
            return
        section = self.sections.setdefault(name, [])
        if len(section) % 2 == 0 and self.scanned >= (section or [0])[-1]:
            section.append(self.scanned)

    def section(self, name: str, instance: int = None):
        """Get section of a File."""
        return Sectioned.get_section(self, name, instance=instance)

    # -----------------------------------------------

    @staticmethod
    def get_index(index: int, length: int, right: bool = False) -> int:
        """Check index, get positive index of negative indexing.
        right=True allows (index == length) and negative index right shift by 1
        """
        ix = index - right * (int(index >= 0) - int(index == 0))
        if abs(ix) - int(ix < 0) >= length + right * int(index < 0):
            ERROR(
                f'index {index} is out of range for length of {length}',
                IndexError,
            )
        return ix + length * int(ix < 0) + right * int(index != 0)

    @staticmethod
    def get_section(File, name, start_byte=0, end_byte=-1, instance=None):
        """Get section of File."""
        # check section name
        try:
            _sect = File.sections[name]
        except KeyError:
            allkeys = list(File.sections.keys())
            ERROR(
                f"section '{name}' not found, choose from {allkeys}", KeyError
            )
        # add EOF to incomplete section
        if len(_sect) % 2:
            _sect = _sect.copy() + [File.scanned]
        # check index and handle negative indexing
        start = File.get_index(start_byte, File.scanned, right=True)
        end = File.get_index(end_byte, File.scanned, right=True)
        if start >= end:
            ERROR(f"invalid byte-range [{start_byte}, {end_byte}]", IndexError)
        # get relevant byte positions
        _sect = np.array(_sect).reshape(-1, 2)
        a0 = np.searchsorted(_sect[:, 0], start)
        a1 = np.searchsorted(_sect[:, 1], end + 1) - 1
        N = _sect.shape[0]
        # no instances found
        if a0 >= N or a1 >= N or a0 < 0 or a1 < 0:
            ERROR(f"no '{name}' section", KeyError)
        # one instance
        elif a0 == a1:
            a, b = _sect[a0]
            return Section(File, a, b - a, name)
        # multiple instances
        else:
            if instance is not None:
                a, b = _sect[instance]
                return Section(File, a, b - a, name)
            else:
                num_instances = a1 - a0 + 1
                instances = []
                for instance in range(num_instances):
                    a, b = _sect[instance]
                    instances.append(Section(File, a, b - a, name))
                return Sections(instances)


class MultiFrames(Sectioned):
    def __len__(self):
        # total num of frames
        return int(0.5 * (len(self.sections.get('frame', [])) + 1))

    def __getitem__(self, indexing):
        frames = self.section('frame')
        if isinstance(frames, Section):
            return frames
        return frames.__getitem__(indexing)


# -----------------------------------------------


class Fortran_unformatted:
    """Fortran unformatted binary format.

    The file consists of blocks where each block
    has the following structure::

        4 bytes int32 delimiter    # block size
        block                      # data
        4 bytes int32 delimiter    # block size

    """

    @staticmethod
    def get_block(fh, dtype='int32'):
        """Get the next block.

        Returns:
            A tuple containing::

                Size (bytes), Content (a list of int32)
        """
        size = np.dtype(dtype).itemsize

        m1 = int(np.squeeze(np.fromfile(fh, dtype=dtype, count=1)))
        b = np.fromfile(fh, dtype=np.dtype(dtype, m1), count=int(m1 / size))
        m2 = int(np.squeeze(np.fromfile(fh, dtype=dtype, count=1)))

        if m1 != m2:
            # opening and ending delimiters are different
            ERROR('start & end of block %d != %d' % (m1, m2), ValueError)
        logger.debug(f'block_size {m1} bytes')

        return (m1, b)

    @staticmethod
    def put_block(fh, dtype, alist):
        """Write a list or array to a new block."""
        b = np.array(alist, dtype=dtype)
        m = np.array(b.size * np.dtype(dtype).itemsize, dtype='int32')
        m.tofile(fh)
        b.tofile(fh)
        m.tofile(fh)
        return

    @staticmethod
    def to_str(m, b):
        return b.view(np.dtype(f'S{m}'))[0].decode('utf-8')

    @staticmethod
    def to_float(d, b):
        return b.view(np.dtype(f'float{d}'))
