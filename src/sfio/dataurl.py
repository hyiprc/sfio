import ast
import base64
import re
from collections.abc import Iterable
from itertools import chain
from pydoc import locate

from . import ERROR

pattern = {
    # file://
    'fileurl': r'(file:\/\/\S+)',
    # data:[<MIME type>][;base64],<data>
    'dataurl': r'data:(?:([a-zA-Z]+)\/?([-+.:=\w]+))?(;base64)?,(.*)',
    # float('nan'), float('inf'), float('-inf)
    'naninf': r"^float\('(-?(?:inf|nan))'\)$",
}
pattern = {k: re.compile(v) for k, v in pattern.items()}


# ---------- Custom Encoder/Decoder ----------

import os
from urllib.parse import urlparse
from urllib.request import url2pathname

import numpy as np

from . import abspath


def cvt_ndarray(array):  # numpy array
    shape = 'x'.join(map(str, array.shape)).replace(' ', '')
    return {
        '__meta__': f":{array.dtype}:shape={shape}",
        '__data__': np.ascontiguousarray(array).data,
    }


def icvt_ndarray(data, subtyp=None):  # numpy array
    _, dtype, shape = subtyp.split(':')[:3]
    shape = tuple(map(int, shape[6:].split('x')))
    return np.frombuffer(data, dtype=dtype).reshape(shape)


def cvt_slice(slc):  # slice object
    return [slc.start, slc.stop, slc.step]


def icvt_slice(data):  # slice object
    return slice(*data)


def cvt_path(path):  # file path
    return abspath(path).as_uri()


def icvt_path(uri):  # file path
    parsed = urlparse(uri)
    host = "{0}{0}{mnt}{0}".format(os.path.sep, mnt=parsed.netloc)
    return abspath(host) / url2pathname(parsed.path)


def cvt_bytes(byte):  # bytes to string
    return byte.decode('utf-8')


# --------------------------------------------

skip_types = (int, complex, type(None))

change_types = {
    'dict_keys': list,
    'numpy.intc': int,
    'numpy.int32': int,
    'numpy.int64': int,
    'numpy.float32': float,
    'numpy.float64': float,
    'bytes': cvt_bytes,
}

custom_convert = {
    # clstyp: (encoder, decoder)
    'slice': (cvt_slice, icvt_slice),
    'pathlib.PosixPath': (cvt_path, icvt_path),
    'pathlib.WindowsPath': (cvt_path, icvt_path),
    'numpy.ndarray': (cvt_ndarray, icvt_ndarray),
    # TODO: use standard image/jpg data url to handle images
    'imageio.core.util.Array': (cvt_ndarray, icvt_ndarray),
}


# --------------------------------------------


def _encode_object(obj):
    meta, data = '', obj

    clstyp = str(type(obj)).split()[-1][1:-2]
    handler = custom_convert.get(clstyp, (None, None))[0]
    if handler is not None:
        data = handler(obj)
        if isinstance(data, dict):
            meta = data.get('__meta__', '')
            data = data.get('__data__', data)
    try:
        if ast.literal_eval(str(data)) == data:
            data = str(data).replace(' ', '')
    except Exception:
        if handler is None:
            ERROR(f"no '{clstyp}' encoder for {repr(obj)}")

    return (clstyp, meta, data)


def encode(obj, b64: bool = False):
    clstyp = str(type(obj)).split()[-1][1:-2]
    obj = change_types.get(clstyp, lambda _: _)(obj)

    if isinstance(obj, (str,) + skip_types):
        # e.g., str, complex, null
        return obj

    elif isinstance(obj, float):
        # nan, inf, -inf are not supported by JSON
        if np.isnan(obj):
            return "float('nan')"
        elif np.isinf(obj):
            sign = '-' * (obj < 0)
            return f"float('{sign}inf')"
        return obj

    elif isinstance(obj, list):
        # recursively encode items in list
        return [encode(s) for s in obj]

    elif isinstance(obj, dict):
        # recursively encode values in dict
        return {k: encode(v) for k, v in obj.items()}

    elif isinstance(obj, (tuple, set)):
        # recursively encode items but do not return
        data = type(obj)([encode(s) for s in obj])

    else:
        data = obj

    # encode objects
    clstyp, meta, data = _encode_object(data)

    # file url
    if clstyp.startswith('pathlib.'):
        return data

    # base64 encoding
    if b64 or not isinstance(data, str):
        if isinstance(data, str):
            data = data.encode('utf-8')
        data = base64.b64encode(data).decode('utf-8')
        b64 = ';base64'
    else:
        b64 = ''

    return f"data:python/{clstyp}{meta}{b64},{data}"


def _decode_url(url):
    # handle file url (file://)
    match_fileurl = pattern['fileurl'].match(url)
    if match_fileurl:
        return icvt_path(match_fileurl[0])

    # skip if not data url (data:,)
    match_dataurl = list(chain(*pattern['dataurl'].findall(url)))
    if not match_dataurl:
        return url
    else:
        typ, subtyp, b64, data = match_dataurl

    # undo base64 encoding
    if b64:
        data = base64.b64decode(data.encode('utf-8'))
        # try:
        #    data = data.decode('utf-8')
        # except UnicodeDecodeError:
        #    pass

    # skip objects not encoded here
    if not typ == 'python':
        return data

    # build-in Python data type?
    try:
        data = ast.literal_eval(data)
    except Exception:
        pass

    # custom conversion
    clstyp = subtyp.split(':')[0]
    handler = custom_convert.get(clstyp, (None, None))[1]
    if handler is not None:
        try:
            return handler(data, subtyp)
        except TypeError:
            return handler(data)

    # decode every item in iterable
    if isinstance(data, Iterable) and not isinstance(data, str):
        return type(data)([decode(s) for s in data])

    return locate(subtyp)(data)


def decode(data):
    if isinstance(data, skip_types):
        # e.g., int, complex, null
        return data

    elif isinstance(data, dict):
        # recursively decode values in dict
        return {k: decode(v) for k, v in data.items()}

    elif isinstance(data, (list, tuple, set)):
        # recursively decode items
        return type(data)([decode(s) for s in data])

    elif isinstance(data, (str, bytes)):
        # nan, inf, -inf
        match_naninf = pattern['naninf'].findall(data)
        if match_naninf:
            return float(match_naninf.pop())
        # decode file url and data url
        return _decode_url(data)

    else:
        return data


# --------------------------------------------


def convert_old_dict_style(dct):
    # for old dict style support only
    try:
        clstyp = dct['__type__']
        data = dct['__data__']

        if clstyp == 'numpy.ndarray':
            return encode(
                np.frombuffer(
                    base64.b64decode(data['array'].encode('utf-8')),
                    dtype=data['dtype'],
                ).reshape(data['shape'])
            )

        handler = custom_convert.get(clstyp, (None, None))[1]
        if handler is not None:
            return encode(handler(data))
        else:
            return encode(locate(clstyp)(data))
    except Exception:
        return dct
