"""Type mapping between Python and SQLite for the game server.

The codebase reads and writes values the way asyncpg does for PostgreSQL:

* ``TIMESTAMP`` / ``TIMESTAMPTZ`` columns come back as **timezone-aware**
  ``datetime`` objects in UTC (``member.last_login.timestamp()`` is called on
  them, so a naive datetime or a string would raise).
* ``BOOLEAN`` columns come back as **int** (0/1), because the generated
  protobuf runtime rejects ``bool`` for int32/int64 fields and handlers assign
  DB values straight into proto fields.

SQLite has neither type, so both are emulated here: timestamps are stored as
TEXT in UTC, booleans as INTEGER 0/1.

Timestamp format
----------------
``'YYYY-MM-DD HH:MM:SS'`` with ``.ffffff`` appended only when non-zero.

That exact shape matters for two reasons:

1. It is what SQLite's own ``CURRENT_TIMESTAMP`` produces, so comparisons such
   as ``expires_at > NOW()`` (rewritten to ``expires_at > CURRENT_TIMESTAMP``)
   stay lexicographically correct.
2. Omitting the fractional part when it is zero keeps ``expires_at > NOW()``
   false at the exact expiry instant instead of off by a sub-second.

Python's ``datetime.isoformat()`` is deliberately *not* used: its ``T``
separator (0x54) sorts above the space (0x20) and would invert comparisons
against ``CURRENT_TIMESTAMP``.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3

_TS_BASE = "%Y-%m-%d %H:%M:%S"
_TS_FULL = "%Y-%m-%d %H:%M:%S.%f"

# Formats accepted when reading back a timestamp column. ISO-8601 with a 'T'
# is included because a value may have been written by tooling that used
# isoformat() rather than this module.
_TS_READ_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)

_UTC = _dt.timezone.utc
_registered = False


def _adapt_datetime(value: _dt.datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(_UTC).replace(tzinfo=None)
    if value.microsecond:
        return value.strftime(_TS_FULL)
    return value.strftime(_TS_BASE)


def _adapt_date(value: _dt.date) -> str:
    return value.strftime("%Y-%m-%d")


def _adapt_bool(value: bool) -> int:
    return 1 if value else 0


def _to_text(value) -> str:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", "replace")
    return str(value)


def _convert_timestamp(value) -> _dt.datetime | None:
    """Parse a stored timestamp into a UTC-aware datetime."""
    if value is None:
        return None
    text = _to_text(value).strip()
    if not text:
        return None
    # A bare integer is treated as a Unix epoch, which is the representation
    # several BIGINT columns in this schema already use.
    try:
        return _dt.datetime.fromtimestamp(int(text), tz=_UTC)
    except (ValueError, OverflowError, OSError):
        pass
    for fmt in _TS_READ_FORMATS:
        try:
            return _dt.datetime.strptime(text, fmt).replace(tzinfo=_UTC)
        except ValueError:
            continue
    try:
        return _dt.datetime.fromisoformat(text).replace(tzinfo=_UTC)
    except ValueError:
        return None


def _convert_date(value):
    if value is None:
        return None
    text = _to_text(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _adapt_list(value: list) -> str:
    """Python list -> JSON text.

    PostgreSQL ARRAY columns (e.g. ``commanders.loading_pic_id_list_1``) are
    created as TEXT on SQLite; the codebase binds plain Python lists to them
    exactly as it binds them to asyncpg ARRAY parameters, so the adapter
    serializes instead of rejecting the bind.
    """
    import json

    return json.dumps(value)


def _adapt_json_object(value: dict) -> str:
    """Python dict -> JSON text (bind side of JSON columns)."""
    import json

    return json.dumps(value)


def register() -> None:
    """Install the adapters/converters. Safe to call repeatedly."""
    global _registered
    if _registered:
        return

    sqlite3.register_adapter(_dt.datetime, _adapt_datetime)
    sqlite3.register_adapter(_dt.date, _adapt_date)
    sqlite3.register_adapter(bool, _adapt_bool)
    sqlite3.register_adapter(list, _adapt_list)
    sqlite3.register_adapter(dict, _adapt_json_object)

    for name in ("timestamp", "timestamptz", "datetime", "timestamp with time zone"):
        sqlite3.register_converter(name, _convert_timestamp)
    for name in ("date",):
        sqlite3.register_converter(name, _convert_date)
    # NOTE: no "json"/"jsonb" READ converter. SQLAlchemy columns typed as JSON
    # deserialize in their own result processor, and raw store.fetch* paths
    # mirror psycopg2 behaviour by handing the caller the JSON TEXT (the
    # codebase's _load_json helpers json.loads it, exactly like on PG).
    # A converter here would make SA's processor receive an already-parsed
    # dict and crash ("the JSON object must be str, bytes...").

    _registered = True
