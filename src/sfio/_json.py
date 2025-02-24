import json
from collections import OrderedDict

from . import ERROR, abspath, dataurl, logger
from .base import ReadWrite


class Json(ReadWrite):
    """JavaScript Object Notation"""

    allow_cache = False

    def scan(self):
        pass

    def parse(self, section, dtype='dict'):
        fpath = self.name
        for codec in ['utf-8', 'windows-1254']:
            try:
                open(fpath, encoding=codec).read()
                break
            except Exception:
                continue
        with open(fpath, encoding=codec) as f:
            try:
                ordered = self.kwargs.get('ordered', True)
                output = load(f, ordered=ordered)
            except json.decoder.JSONDecodeError:
                ERROR(f"cannot parse {fpath}")
        logger.debug(f'read json file {fpath}')
        return output

    @classmethod
    def write(cls, fpath, data, **kwargs):
        """write adict to json file"""
        fpath = abspath(fpath)
        with open(fpath, 'w', encoding='utf8') as f:
            dump(
                data,
                f,
                indent=kwargs.get('indent', 4),  # pretty print
                ensure_ascii=False,
            )
        logger.debug(f'wrote json file\n  {fpath}')
        return fpath


# -------------------------------------------------------------


class encoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            return dataurl.encode(obj)


def decoder(dct):
    try:
        dct = OrderedDict(dct)
    except Exception:
        return dct
    return dataurl.decode(dct)


# -------------------------------------------------------------


def dumps(*args, **kwargs):
    kwargs.setdefault('cls', encoder)
    return json.dumps(*args, **kwargs)


def loads(*args, **kwargs):
    if kwargs.pop('ordered', True):
        kwargs.setdefault('object_pairs_hook', decoder)
    else:
        kwargs.setdefault('object_hook', dataurl.decode)
    return json.loads(*args, **kwargs)


def dump(*args, **kwargs):
    kwargs.setdefault('cls', encoder)
    return json.dump(*args, **kwargs)


def load(*args, **kwargs):
    if kwargs.pop('ordered', True):
        kwargs.setdefault('object_pairs_hook', decoder)
    else:
        kwargs.setdefault('object_hook', dataurl.decode)
    return json.load(*args, **kwargs)


# -------------------------------------------------------------


from hashlib import sha256 as hashfunc


def hash(d: dict, n: int = 10):
    return hashfunc(
        dumps(
            d,
            sort_keys=True,
            ensure_ascii=True,
            separators=(',', ':'),
        ).encode('utf')
    ).hexdigest()[:n]


def serialize(adict):
    """serialize a dict"""
    return json.loads(dumps(adict))


def deserialize(adict):
    """de-serialize a dict"""
    return loads(json.dumps(adict))
