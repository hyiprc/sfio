__all__ = ['flatten', 'search_in_file']

import re
from itertools import chain


def flatten(iterable):
    return list(_flatten(iterable))


def _flatten(iterable):
    """flatten deeply nested iterables"""
    # return item if one item only
    try:
        if isinstance(iterable, (str, bytes)):
            raise TypeError
        iterator = iter(iterable)
    except TypeError:
        yield iterable
        return
    # multiple items, loop through them
    while True:
        try:
            i = next(iterator)
            if isinstance(i, (str, bytes)):
                raise TypeError
            iterator = chain(iter(i), iterator)
        except TypeError:
            yield i
        except StopIteration:
            break


def search_in_file(fd, patterns, seek=0, bufsize=1e6):
    """Search patterns in a file chunk-by-chunk. Return starting byte positions."""
    patterns = list(flatten(patterns))
    matches = [[] if isinstance(b, bytes) else None for b in patterns]

    # remove invalid patterns, compile regex, and get num_bytes to overlap chunks
    pats = [(i, b) for i, b in enumerate(patterns) if isinstance(b, bytes)]
    searches = [re.compile(b'^.*' + pat, re.M) for _, pat in pats]
    overlap = max([len(pattern[1]) for pattern in pats])

    # adjust buffer size to ensure len(pattern) < bufsize
    bufsize = int(bufsize * (overlap // bufsize + 1))

    # start searching from seek position
    last_start = fd.seek(seek)
    while True:
        buf = fd.read(bufsize)
        pos0 = fd.tell() - len(buf)
        for (i, pat), search in zip(pats, searches):
            pos = [pos0 + s.start() for s in re.finditer(search, buf)]
            matches[i].extend(pos)
        next_start = fd.tell() - overlap + 1

        # termination
        if next_start == last_start:
            # remove duplicates while maintaining order
            return [
                list(dict.fromkeys(v)) if v is not None else None
                for v in matches
            ]

        # continue to the next chunk
        last_start = next_start
        fd.seek(next_start)
