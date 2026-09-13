"""Safe datetime-to-unix helpers.

``datetime.timestamp()`` can raise ``OSError: [Errno 22]`` on Windows for
edge-case dates (very old / very far future / timezone-naive values near the
epoch).  All call sites that convert DB-loaded datetimes to protobuf uint32
timestamps should use ``safe_ts()`` instead of bare ``.timestamp()``.
"""

from __future__ import annotations

import datetime as _dt


def safe_ts(dt: _dt.datetime | None, default: int = 0) -> int:
    """Return ``int(dt.timestamp())`` or *default* on any conversion error.

    A timezone-naive datetime is interpreted as UTC (that is what the DB layer
    stores): ``.timestamp()`` would otherwise apply the machine's local UTC
    offset -- wrong by hours on non-UTC hosts, and ``OSError: [Errno 22]`` on
    Windows for pre-epoch values such as the ``1970-01-01`` defaults.
    """
    if dt is None:
        return default
    if isinstance(dt, _dt.datetime) and dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    try:
        return int(dt.timestamp())
    except (OSError, ValueError, OverflowError, TypeError, AttributeError):
        return default
