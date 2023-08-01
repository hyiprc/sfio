__all__ = ['ReadOnly', 'ReadWrite', 'MultiFrames', 'Fortran_unformatted']

import abc
import gzip

from . import logger


class FileType(abc.ABC):
    @classmethod
    def open(cls, fpath, *args, **kwargs):
        # handle compressed file
        zipped = fpath.suffix == ".gz"
        _open = gzip.open if zipped else open
        return _open(fpath, *args, **kwargs)

    @classmethod
    def read(cls, fpath):
        return cls(fpath)

    @abc.abstractmethod
    def parse(self, *args, **kwargs):
        pass


class ReadOnly(FileType):
    @classmethod
    def write(cls, *args, **kwargs):
        raise NotImplementedError(f"{cls.__name__} file format is ReadOnly")


class ReadWrite(FileType):
    @classmethod
    @abc.abstractmethod
    def write(cls, *args, **kwargs):
        pass


# -----------------------------------------------


class MultiFrames:
    @classmethod
    def init_frames(cls, fileobj, split_frames=None):
        _fr = []
        print(fileobj.mode)
        is_read_mode = fileobj.mode == 1 or 'r' in str(fileobj.mode)
        if is_read_mode and split_frames and split_frames is not None:
            # record starting position of each frame
            Nbyte = 0
            for line in fileobj:
                if split_frames(line):
                    _fr.append(Nbyte)
                Nbyte += len(line)
            _fr.append(Nbyte)
        return _fr

    def __len__(self):
        return len(self._fr) - 1  # total num of frames

    def __iter__(self):
        for fr in range(len(self)):
            yield self[fr]

    def __getitem__(self, fr):
        if isinstance(fr, int):
            return self.parse_frame(fr)

        if isinstance(fr, slice):
            # index out of range?
            if fr.start is not None:
                self.get_frame_index(fr.start)
            if fr.stop is not None:
                self.get_frame_index(fr.stop - int(fr.stop > 0))

            frames = range(len(self))[fr]

        elif isinstance(fr, list):
            fr = list(map(int, fr))
            frames = [self.get_frame_index(i) for i in fr]

        # single frame
        if len(frames) == 1:
            return self.parse_frame(frames[0])

        # entire range, no slicing or indexing
        elif (
            len(frames) == len(self)
            and frames[-1] > frames[0]
            and np.all(np.diff(frames) == 1)
        ):
            return self

        # slicing or indexing
        else:
            if not isinstance(self, View):
                return View(self, frames)
            try:
                frames = [self.frames[i] for i in frames]
            except IndexError:
                raise IndexError(
                    f"index out of range, frames_in_view={self.frames}"
                )
            return View(self.root, frames)

    # -----------------------------------------------

    def get_frame_index(self, fr):
        Nfr = len(self)
        if abs(fr) - int(fr < 0) >= Nfr:
            raise IndexError(f'{Nfr} frames, index ({fr}) is out of range')
        ifr = fr + Nfr * int(fr < 0)
        return ifr

    def read_frame(self, fr, asbytes=True):
        ix = self.get_frame_index(fr)
        if isinstance(self, View):
            ix = self.frames[ix]
        with self.open(self.fpath, 'rb') as f:
            f.seek(self._fr[ix])
            fbytes = f.read(self._fr[ix + 1] - self._fr[ix])
        if asbytes:
            return fbytes
        fstr = fbytes.decode().rstrip()
        return fstr

    def parse_frame(self, fr):
        return self.parse(self.read_frame(fr, asbytes=False))


class View(MultiFrames):
    """for slicing and indexing"""

    def __init__(self, root, frames):
        self.frames = frames
        self.root = root
        self.fpath = root.fpath
        self.open = root.open
        self._fr = root._fr
        self.parse = root.parse

    def __len__(self):
        return len(self.frames)


# -----------------------------------------------

import numpy as np


class Fortran_unformatted:
    """Fortran unformatted binary format.

    The file consists of blocks where each block
    has the following structure::

        4 bytes int32 delimiter    # block size
        block                      # data
        4 bytes int32 delimiter    # block size

    """

    def __init__(self, fpath, **kwargs):
        # process args
        kwargs.setdefault('mode', 'rb')
        self.f = open(fpath, **kwargs)
        self.fpath = fpath

    def _get_block(self):
        """Get the next block.

        Returns:
            A tuple containing::

                Size (bytes), Content (a list of int32)
        """
        try:
            self.Nblock += 1
        except Exception:
            self.Nblock = 0
        size = np.dtype('int32').itemsize
        m1 = int(np.fromfile(self.f, dtype='int32', count=1))
        b = np.fromfile(
            self.f, dtype=np.dtype('int32', m1), count=int(m1 / size)
        )
        m2 = int(np.fromfile(self.f, dtype='int32', count=1))
        if m1 != m2:
            # opening and ending delimiters are different
            raise ValueError('error, start & end of block %d != %d' % (m1, m2))
        logger.debug(f'\nb{self.Nblock} {m1}\n{b}')
        return (m1, b)

    def _put_block(self, dtype, alist):
        """Write a list or array to a new block."""
        b = np.array(alist, dtype=dtype)
        m = np.array(b.size * np.dtype(dtype).itemsize, dtype='int32')
        m.tofile(self.f)
        b.tofile(self.f)
        m.tofile(self.f)
        return

    def _to_str(self, m, b):
        return b.view(np.dtype(f'S{m}'))[0].decode('utf-8')

    def _to_float(self, m, b):
        return b.view(np.dtype(f'float{m}'))
