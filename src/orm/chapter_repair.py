from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from src.db.session import get_sync_session

_REPAIR_FREE_COUNT = 1
_REPAIR_CHARGE_COUNT = 3
_REPAIR_TOTAL_COUNT = _REPAIR_FREE_COUNT + _REPAIR_CHARGE_COUNT
_REPAIR_GEM_COST = 100
_REPAIR_GEM_RESOURCE_ID = 4




def _region_location():
    try:
        from src.shopreset.framework import _current_region_location
        return _current_region_location()
    except Exception:
        from datetime import timezone
        return timezone.utc


def _current_reset_key() -> str:
    return datetime.now(_region_location()).strftime("%Y-%m-%d")


def get_daily_repair_count(commander_id: int) -> int:
    key = _current_reset_key()
    with get_sync_session() as session:
        row = session.execute(
            text(
                "SELECT count, reset_key FROM commander_daily_repair_states "
                "WHERE commander_id = :cid"
            ),
            {"cid": commander_id},
        ).first()
    if row is None:
        return 0
    if row[1] != key:
        return 0
    return int(row[0]) if row[0] is not None else 0


def increment_daily_repair_count(commander_id: int, amount: int = 1) -> None:
    if amount <= 0:
        return
    key = _current_reset_key()
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_daily_repair_states (commander_id, count, reset_key)
                VALUES (:cid, :amount, :key)
                ON CONFLICT (commander_id)
                DO UPDATE SET
                    count = CASE
                        WHEN commander_daily_repair_states.reset_key = EXCLUDED.reset_key
                            THEN commander_daily_repair_states.count + EXCLUDED.count
                        ELSE EXCLUDED.count
                    END,
                    reset_key = EXCLUDED.reset_key,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {"cid": commander_id, "amount": amount, "key": key},
        )
        session.commit()


def repair_limits() -> tuple[int, int, int, int]:
    return _REPAIR_FREE_COUNT, _REPAIR_CHARGE_COUNT, _REPAIR_TOTAL_COUNT, _REPAIR_GEM_COST
