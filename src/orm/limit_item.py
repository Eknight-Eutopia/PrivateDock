"""Per-commander "limit item" counts sent via SC_15001.limit_list.

The EN client reads Specialized Cores (item 59010, the real item behind the
virtual proxy 59011) from ``BagProxy:GetLimitCntById(59010)`` for the UR
exchange page, overflow warnings, and the monthly "obtain X cores" tasks. That
count is tracked here, bucketed by region-local month so it naturally resets
each month (matching the original monthly tally / 5000 cap display). Only the
Specialized Core uses this mechanism in the current client.
"""

from __future__ import annotations

from sqlalchemy import text

from src.db.session import get_sync_session
from src.region.region import local_now

SPECIALIZED_CORE_ITEM_ID = 59010
SPECIALIZED_CORE_VITEM_ID = 59011


def month_bucket(now=None) -> int:
    """Region-local YYYYMM bucket for a timestamp (defaults to now)."""
    dt = now or local_now()
    return dt.year * 100 + dt.month


def add_limit_item(commander_id: int, item_id: int, count: int) -> None:
    """Add ``count`` to the current month's limit tally for ``item_id``.

    A second, month_bucket=0 "lifetime" row is maintained alongside the
    monthly one: the Handbook "Obtain a total of N Specialized Cores" tasks
    (sub_type 130) read the lifetime total via _sync_possession_tasks_sync.
    Monthly readers (SC_15001.limit_list) always filter by the current
    bucket and never see the lifetime row."""
    if count <= 0:
        return
    bucket = month_bucket()
    with get_sync_session() as session:
        for bkt in (bucket, 0):
            session.execute(
                text(
                    "INSERT INTO commander_limit_items (commander_id, item_id, month_bucket, count) "
                    "VALUES (:cid, :iid, :bucket, :cnt) "
                    "ON CONFLICT (commander_id, item_id, month_bucket) "
                    "DO UPDATE SET count = commander_limit_items.count + EXCLUDED.count, "
                    "updated_at = CURRENT_TIMESTAMP"
                ),
                {"cid": commander_id, "iid": item_id, "bucket": bkt, "cnt": count},
            )
        session.commit()


def get_limit_item_count(commander_id: int, item_id: int) -> int:
    """Current month's limit tally for ``item_id`` (0 if none yet)."""
    bucket = month_bucket()
    with get_sync_session() as session:
        row = session.execute(
            text(
                "SELECT count FROM commander_limit_items "
                "WHERE commander_id = :cid AND item_id = :iid AND month_bucket = :bucket"
            ),
            {"cid": commander_id, "iid": item_id, "bucket": bucket},
        ).first()
        return int(row[0]) if row else 0
