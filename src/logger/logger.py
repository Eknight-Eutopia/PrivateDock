import os
import re
import sys
import threading
import time
from datetime import datetime
from typing import Optional
from colorama import init as colorama_init
from colorama import Fore
from colorama import Style

colorama_init()

LOG_LEVEL_DEBUG = 0
LOG_LEVEL_INFO = 1
LOG_LEVEL_WARN = 2
LOG_LEVEL_ERROR = 3


class Field:
    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value


class Entry:
    def __init__(self, scope: str, fields: Optional[list[Field]] = None):
        self.scope = scope
        self.fields = fields or []

    def with_fields(self, *fields: Field) -> "Entry":
        new_fields = self.fields.copy()
        new_fields.extend(fields)
        return Entry(self.scope, new_fields)

    def debug(self, message: str):
        log(self.scope, message, LOG_LEVEL_DEBUG, *self.fields)

    def info(self, message: str):
        log(self.scope, message, LOG_LEVEL_INFO, *self.fields)

    def warn(self, message: str):
        log(self.scope, message, LOG_LEVEL_WARN, *self.fields)

    def error(self, message: str):
        log(self.scope, message, LOG_LEVEL_ERROR, *self.fields)


_log_level: Optional[int] = None

_session_start = datetime.now()
_log_stream_name: Optional[str] = None
_log_file = None
_log_file_lock = threading.Lock()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _project_root() -> str:
    # src/logger/logger.py -> project root
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def init_file_logging(stream: str, log_dir: Optional[str] = None):
    """Enable per-session file logging: creates <root>/logs/<stream>_<YYYYmmdd_HHMMSS>.log.

    Called once at startup by each entrypoint (e.g. stream="gateway" or "server").
    Safe to call multiple times; only the first call takes effect.
    """
    global _log_stream_name, _log_file
    with _log_file_lock:
        if _log_file is not None:
            return
        _log_stream_name = stream
        try:
            d = log_dir or os.path.join(_project_root(), "logs")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, f"{stream}_{_session_start.strftime('%Y%m%d_%H%M%S')}.log")
            _log_file = open(path, "a", encoding="utf-8", errors="replace")
        except Exception as e:
            _log_file = None
            print(f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | ERROR | logger | failed to open log file: {e}", file=sys.stderr)
            return
        print(f"logging to file: {path}", file=sys.stdout)


def _write_file(line: str):
    f = _log_file
    if f is None:
        return
    try:
        f.write(_ANSI_RE.sub("", line) + "\n")
        f.flush()
    except Exception:
        pass


def _active_log_path() -> Optional[str]:
    f = _log_file
    if f is None:
        return None
    try:
        return os.path.abspath(f.name)
    except Exception:
        return None


def cleanup_logs(
    log_dir: Optional[str] = None,
    max_age_days: int = 14,
    max_total_mb: int = 30,
) -> tuple[int, int]:
    """Delete stale log files from the logs directory.

    Called once at server startup, after the current session's log file has
    been opened. Two independent rules (each disabled by a value <= 0):
    files whose last modification is older than ``max_age_days`` are removed,
    then oldest-first removal trims the directory down to ``max_total_mb``.
    The active session's log file is never deleted even when it alone exceeds
    the cap. Returns (deleted_count, freed_bytes).
    """
    d = log_dir or os.path.join(_project_root(), "logs")
    if not os.path.isdir(d):
        return 0, 0

    active = _active_log_path()
    now = time.time()
    entries: list[tuple[str, float, int]] = []
    total = 0
    for name in os.listdir(d):
        if not name.lower().endswith(".log"):
            continue
        path = os.path.abspath(os.path.join(d, name))
        try:
            st = os.stat(path)
        except OSError as e:
            print(f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | ERROR | logger | log cleanup: cannot stat {path}: {e}", file=sys.stderr)
            continue
        entries.append((path, st.st_mtime, st.st_size))
        total += st.st_size

    deleted = 0
    freed = 0

    def _remove(path: str, size: int) -> bool:
        nonlocal deleted, freed, total
        try:
            os.remove(path)
        except OSError as e:
            print(f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | ERROR | logger | log cleanup: cannot delete {path}: {e}", file=sys.stderr)
            return False
        deleted += 1
        freed += size
        total -= size
        return True

    if max_age_days > 0:
        cutoff = now - max_age_days * 86400
        kept: list[tuple[str, float, int]] = []
        for path, mtime, size in entries:
            if path != active and mtime < cutoff:
                if _remove(path, size):
                    continue
            kept.append((path, mtime, size))
        entries = kept

    if max_total_mb > 0:
        limit = max_total_mb * 1024 * 1024
        for path, _mtime, size in sorted(entries, key=lambda e: e[1]):
            if total <= limit:
                break
            if path == active:
                continue
            _remove(path, size)

    return deleted, freed


def _get_log_level() -> int:
    global _log_level
    if _log_level is not None:
        return _log_level
    level_map = {
        "debug": LOG_LEVEL_DEBUG,
        "info": LOG_LEVEL_INFO,
        "warn": LOG_LEVEL_WARN,
        "warning": LOG_LEVEL_WARN,
        "error": LOG_LEVEL_ERROR,
    }
    _log_level = level_map.get(os.environ.get("LOG_LEVEL", "").lower(), LOG_LEVEL_DEBUG)
    return _log_level


def scope(name: str) -> Entry:
    return Entry(name)


def with_fields(scope: str, *fields: Field) -> Entry:
    return Entry(scope, list(fields))


def field_value(key: str, value) -> Field:
    return Field(key, str(value))


def packet_fields(packet_id: int, direction: str) -> list[Field]:
    return [
        Field("packet", str(packet_id)),
        Field("dir", direction),
    ]


def commander_fields(commander_id: int, account_id: int) -> list[Field]:
    return [
        Field("commander", str(commander_id)),
        Field("account", str(account_id)),
    ]


_LEVEL_LABELS = ["DEBUG", "INFO", "WARN", "ERROR"]
_LEVEL_COLORS = {
    LOG_LEVEL_DEBUG: Fore.BLUE,  # blue
    LOG_LEVEL_INFO: Fore.GREEN,   # green
    LOG_LEVEL_WARN: Fore.YELLOW,   # yellow
    LOG_LEVEL_ERROR: Fore.RED,  # red
}
_RESET = Style.RESET_ALL
_BOLD = Style.BRIGHT
_CYAN = Fore.CYAN
_DIM = Style.DIM


def _format_time() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def _format_fields(*fields: Field) -> str:
    if not fields:
        return ""
    parts = []
    for f in fields:
        k = f.key
        v = f.value if f.value else "-"
        parts.append(f"{k}={v}")
    return " ".join(parts)


def log(scope: str, message: str, level: int = LOG_LEVEL_INFO, *fields: Field):
    if level < _get_log_level():
        return
    ts = _format_time()
    label = _LEVEL_LABELS[level] if level < len(_LEVEL_LABELS) else "UNKNOWN"
    color = _LEVEL_COLORS.get(level, "")
    flds = _format_fields(*fields)
    if flds:
        line = f"{ts} | {color}{_BOLD}{label}{_RESET} | {_CYAN}{_BOLD}{scope}{_RESET} | {_DIM}{flds}{_RESET} | {message}"
    else:
        line = f"{ts} | {color}{_BOLD}{label}{_RESET} | {_CYAN}{_BOLD}{scope}{_RESET} | {message}"
    print(line, file=sys.stdout)
    _write_file(line)


def log_event(category: str, subcategory: str, description: str, level: int = LOG_LEVEL_INFO):
    fields = []
    if subcategory:
        fields.append(Field("event", subcategory))
    sc = f"{category}/{subcategory}" if subcategory else category
    log(sc, description, level, *fields)


def log_raw(line: str):
    """Echo an already-formatted external line (e.g. `adb logcat` output).

    Goes to stdout *and* the session log file, verbatim: the line carries its own
    Android timestamp and must not be re-prefixed, but it does have to be
    persisted.  The adb watcher prints logcat from a background thread, so
    without this a client crash trace was visible only on the live console and
    was gone once the terminal scrolled.
    """
    print(line, file=sys.stdout)
    _write_file(line)
