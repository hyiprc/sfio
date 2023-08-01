__all__ = []

rootname = "fio"

import inspect
import sys
from pathlib import Path


def abspath(path):
    return Path(path).expanduser().resolve().absolute()


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

logger = logging.getLogger(rootname)
logger.setLevel(logging.INFO)

default_screen_level = logging.DEBUG
default_logfile_level = logging.DEBUG + interactive * 999


class FormatterIcon(logging.Formatter):
    def __init__(self, fmt, **kwargs):
        def add_icon(icon):
            with_icon = fmt.replace('%(icon)s', icon)
            return _fmt(with_icon, **kwargs)

        _fmt = logging.Formatter
        self.formatter = _fmt(fmt)
        self.formatters = {
            logging.DEBUG: add_icon('🐛'),
            logging.INFO: add_icon('ℹ️'),
            logging.WARNING: add_icon('⚠️'),
            logging.ERROR: add_icon('❗'),
            logging.CRITICAL: add_icon('🚨'),
        }

    def format(self, record):
        formatter = self.formatters.get(record.levelno, self.formatter)
        return formatter.format(record)


screen = logging.StreamHandler()
screen.setFormatter(FormatterIcon('%(icon)s%(levelname)s: %(message)s'))
screen.setLevel(default_screen_level)
logger.addHandler(screen)

logfile = logging.handlers.WatchedFileHandler(
    cwd / f"{rootname}.log", delay=True
)
logfile.setFormatter(
    FormatterIcon(
        fmt='%(asctime)s.%(msecs)03d (%(processName)s, %(threadName)s) [%(levelname)s]: %(icon)s  %(message)s',
        datefmt="%Y-%m-%d %Z %H:%M:%S",
    )
)
logfile.setLevel(default_logfile_level)
logger.addHandler(logfile)


# -------------------------------------------------------------

import re
import threading
import traceback
from textwrap import indent


def format_exception(e, s, tb):
    if e is None:
        return []

    tb_exc = traceback.format_exception(e, s, tb)
    stack = traceback.format_stack()
    trace_list = tb_exc[:1] + stack[:-1] + tb_exc[1:]

    _s = re.compile(f'File "/.*/src/{rootname}')
    _dir = f'File \"{rootname}.rootdir'
    trace_list = [_s.sub(_dir, s) for s in trace_list]
    if trace_list:
        trace_list[-1] = trace_list[-1].rstrip()

    return trace_list


def excepthook(e, s, tb, msg='uncaught exception'):
    trace_list = format_exception(e, s, tb)
    if f" raise {e.__name__}" in trace_list[-2]:
        msg = trace_list.pop(-1)
        trace_list[-1] = trace_list[-1].rstrip()
    trace_list.pop(1)  # exclude this function from trace
    trace_str = indent(''.join(trace_list), '  ')
    logger.error(f"{msg}\n{trace_str}")


def thread_excepthook(t):
    if t.exc_type == SystemExit:
        return
    excepthook(
        t.exc_type,
        t.exc_value,
        t.exc_traceback,
        msg=f"uncaught exception in {t.thread}",
    )


sys.excepthook = excepthook
threading.excepthook = thread_excepthook  # for python>=3.8


# -------------------------------------------------------------


def ERROR(msg: str = 'no message specified', say=logger.error, **kwargs):
    scn = bool(kwargs.get('screen', True))  # print on screen?
    log = bool(kwargs.get('log', not interactive))  # record in log file?
    seelog = bool(kwargs.get('seelog', log))

    screen_on = default_screen_level + (not scn) * 999
    logfile_on = default_logfile_level + (not log) * 999

    # get traceback and stack
    slic = slice(*kwargs.get('slic', (None, None)))
    e, s, tb = sys.exc_info()
    trace_list = format_exception(e, s, tb)[slic]
    trace_str = '\n' + indent(''.join(trace_list), '  ')

    # turn on screen and logfile
    screen.setLevel(screen_on)
    logfile.setLevel(logfile_on)

    # output messages
    default_trace = int(not interactive) + 1
    trace = int(kwargs.get('trace', default_trace))
    # 0 = only msg, no exception/traceback/stack
    # 1 = exception+traceback+stack
    # 2 = exception on screen, exception+traceback+stack in log
    if not trace_list or trace == 0:
        say(msg)
    elif trace == 2:
        # screen
        logfile.setLevel(999)  # off
        say(f"{msg}\n{indent(trace_list[-1].rstrip(),'  ')}")
        if log and seelog:
            print(f'  see {logfile.baseFilename}')
        # logfile
        screen.setLevel(999)  # off
        logfile.setLevel(logfile_on)
        say(f"{msg}{trace_str}")
    else:
        say(f"{msg}{trace_str}")

    # reset screen and logfile
    screen.setLevel(default_screen_level)
    logfile.setLevel(default_logfile_level)

    # exit?
    if bool(kwargs.get('exit', True)):
        if interactive:
            sys.excepthook = sys.__excepthook__
            sys.tracebacklimit = 0
            raise KeyboardInterrupt
        else:
            raise SystemExit(1)
    return SystemExit


def WARNING(msg: str = 'no message specified', say=logger.warning, **kwargs):
    kwargs['exit'] = False
    return ERROR(msg=msg, say=say, **kwargs)


# -------------------------------------------------------------

if '-m' not in sys.argv:
    from .box import Box  # noqa: F401

from .supported_formats import available


def init(name):
    name = name.strip()
    try:
        info = available[name]
    except KeyError:
        ERROR(f"no file format named '{name}'", trace=1)
    m = __import__(f'{rootname}.{info[0]}', fromlist=[''])
    try:
        return getattr(m, info[1])
    except AttributeError:
        return m


def _filehandler(filepath, name=None):
    if name is None:
        suffixes = Path(filepath).suffixes
        name = ''.join([_ for _ in suffixes if _ != '.gz'])
    return init(name)


def read(filepath, typ=None, **kwargs):
    """read a file, detect file format by file extension"""
    return _filehandler(filepath, typ).read(filepath, **kwargs)


def write(filepath, data, typ=None, **kwargs):
    """write a file, detect file format by file extension"""
    return _filehandler(filepath, typ).write(filepath, data, **kwargs)
