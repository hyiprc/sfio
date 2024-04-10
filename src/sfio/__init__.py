__all__ = []

rootname = "sfio"

import inspect
import sys
from pathlib import Path


def abspath(path):
    return Path(path).expanduser().resolve().absolute()


def relpath(path, parent=Path.cwd()):
    path, parent = Path(path), Path(parent)
    if parent in path.parents or parent == path:
        return path.relative_to(parent)
    return path


rootdir = abspath(inspect.getfile(__import__(rootname))).parent
cwd = Path.cwd()  # launching directory
swd = abspath(sys.path[0])  # script directory

with open(rootdir / 'VERSION') as f:
    __version__ = str(f.readline()).strip()

interactive = hasattr(sys, 'ps1')


# -------------------------------------------------------------


import time


def timestamp():
    return time.time()


def timefmt(timestamp, utc=False, **kwargs):
    def t(fmt, ts):
        return time.strftime(
            kwargs.get('fmt', fmt).format(
                msec=(str(timestamp).split('.') + [0])[1]
            ),
            ts(timestamp),
        )

    if utc:
        return t('%Y-%m-%dT%H:%M:%S.{msec}+00:00', time.gmtime)
    else:
        return t('%Y-%m-%d %Z %H:%M:%S.{msec}', time.localtime)


# -------------------------------------------------------------


import logging
import logging.handlers


class FormatterIcon(logging.Formatter):
    icons = {
        logging.DEBUG: '🐛',
        logging.INFO: 'ℹ️',
        logging.WARNING: '⚠️',
        logging.ERROR: '❗',
        logging.CRITICAL: '🚨',
    }

    def __init__(self, fmt, **kwargs):
        def add_icon(icon):
            with_icon = fmt.replace('%(icon)s', icon)
            return _fmt(with_icon, **kwargs)

        _fmt = logging.Formatter
        self.formatter = _fmt(fmt)
        self.formatters = {k: add_icon(v) for k, v in self.icons.items()}

    def format(self, record):
        formatter = self.formatters.get(record.levelno, self.formatter)
        return formatter.format(record)


formatter_simple = FormatterIcon('%(icon)s%(levelname)s: %(message)s')
formatter_detailed = FormatterIcon(
    fmt='%(asctime)s.%(msecs)03d (%(processName)s, %(threadName)s) [%(levelname)s]: %(icon)s  %(message)s',
    datefmt="%Y-%m-%d %Z %H:%M:%S",
)

screen = logging.StreamHandler()
screen.setFormatter(formatter_simple)
screen.setLevel(logging.NOTSET)

logfile_path = swd / f"{rootname}.log"
logfile = logging.handlers.WatchedFileHandler(logfile_path, delay=True)
logfile.setFormatter(formatter_detailed)
logfile.setLevel(logging.NOTSET + interactive * 999)

logger = logging.getLogger(rootname)
logger.setLevel(logging.INFO)  # INFO, DEBUG for -v, NOTSET for -vv
logger.addHandler(screen)
logger.addHandler(logfile)


# -------------------------------------------------------------


import threading


def _format_exception(e, s, tb):
    import re
    import traceback

    if e is None:
        return []

    tb_exc = traceback.format_exception(e, s, tb)
    stack = traceback.format_stack()
    trace_list_all = tb_exc[:1] + stack[:-1] + tb_exc[1:]

    search = re.compile(f'File "/.*/src/{rootname}')
    replacement = f'File "{{{rootname}.rootdir}}'
    selfstr = r'__init__.py", line \d+, in (ERROR|WARNING|excepthook)'

    exclude = re.compile('|'.join([search.pattern, 'File "<.*>",']))
    always_exclude = re.compile(selfstr)

    trace_list = [
        search.sub(replacement, s)
        for s in trace_list_all
        if (logger.level <= 0 or exclude.search(s) is None)
        and always_exclude.search(s) is None
    ]

    if trace_list:
        trace_list[-1] = trace_list[-1].rstrip()

    return trace_list


def excepthook(e, s, tb, msg='uncaught exception', say=logger.error):
    from textwrap import indent

    if e is KeyboardInterrupt:
        return
    trace_list = _format_exception(e, s, tb)
    trace_str = indent(''.join(trace_list), '  ')
    say(f"{msg}\n{trace_str}")
    if screen.level > logging.CRITICAL and logfile.level <= logging.CRITICAL:
        name = say.__name__.upper()
        icon = FormatterIcon.icons.get(getattr(logging, name, None), '')
        print(f'{icon}{name}: see {relpath(logfile.baseFilename)}')


def thread_excepthook(t):
    if t.exc_type is SystemExit:
        return
    excepthook(
        t.exc_type,
        t.exc_value,
        t.exc_traceback,
        msg=f"uncaught exception in {t.thread}",
    )


sys.excepthook = excepthook  # = sys.__excepthook__ to reset
threading.excepthook = thread_excepthook  # for python>=3.8


# -------------------------------------------------------------


def ERROR(
    msg: str = 'no message specified',
    exception=RuntimeError,
    exit=True,
    say=logger.error,
):
    # get traceback and stack
    e, s, tb = sys.exc_info()
    if e is None:
        try:
            raise exception(msg)
        except Exception:
            (e, s, tb), msg = sys.exc_info(), ''
    excepthook(e, s, tb, msg=msg, say=say)

    # exit?
    if exit and interactive:
        raise KeyboardInterrupt
    elif exit:
        raise SystemExit(1)
    return SystemExit


def WARNING(msg: str = 'no message specified', exception=RuntimeWarning):
    return ERROR(msg, exception, exit=False, say=logger.warning)


# -------------------------------------------------------------


if '-m' not in sys.argv:
    from .box import Box  # noqa: F401

from . import func  # noqa: F401
from .supported_formats import available


def _fileclass(name: str):
    name = name.strip().lower()
    info = available.get(f'.{name}', available.get(name, None))
    if info is None:
        ERROR(f"unknown filetype '{name}'")
    m = __import__(f'{rootname}.{info[0]}', fromlist=[''])
    try:
        return getattr(m, info[1])
    except AttributeError:
        return m


def _filehandler(filepath, name=None):
    import io

    if isinstance(filepath, io.IOBase):
        filepath = filepath.name
    if name is None:
        suffixes = Path(filepath).suffixes
        name = ''.join([_ for _ in suffixes if _ != '.gz'])
    return _fileclass(name)


def init(f, filetype=None, **kwargs):
    File = _filehandler(f, filetype)
    return File(f, **kwargs)


def read(f, filetype=None, **kwargs):
    """read a file, detect file format by file extension"""
    import json

    self = init(f, filetype, **kwargs)
    # try to load file cache
    fcache = Path(f).with_name(f'_{Path(f).name}.cache')
    try:
        cache = json.load(open(fcache))
        self.sections.update(cache.get('sections', {}))
        self.scanned = cache.get('scanned', 0)
        logger.info(f"skipped file scan, read from cache '{fcache.name}'")
    except Exception:
        pass
    # scan sections and write cache
    t0 = timestamp()
    self.scan()
    time_elapsed = timestamp() - t0
    if time_elapsed > 8 and getattr(self, 'allow_cache', True):
        logger.info(
            f"file reading took {time_elapsed:.1f}s"
            f", write cache '{fcache.name}'"
        )
        json.dump(self.cache, open(fcache, 'w'))
    return self


def write(f, data, filetype=None, **kwargs):
    """write a file, detect file format by file extension"""
    return _filehandler(f, filetype).write(f, data, **kwargs)
