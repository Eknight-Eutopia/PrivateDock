from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from src.db.session import get_sync_session
from src.orm.config_entry import get_config_entry, list_config_entries

DAILY_TEMPLATE_CATEGORY = "ShareCfg/expedition_daily_template.json"

_RESET_LIMIT_TYPE_DAILY = 1
_RESET_LIMIT_TYPE_WEEKLY = 2




def _region_location():
    try:
        from src.shopreset.framework import _current_region_location
        return _current_region_location()
    except Exception:
        return timezone.utc


def _current_reset_key(daily_level_id: int) -> str:
    tpl = get_daily_template(daily_level_id) or {}
    limit_type = tpl.get("limit_type", _RESET_LIMIT_TYPE_DAILY)
    loc = _region_location()
    now = datetime.now(loc)
    if limit_type == _RESET_LIMIT_TYPE_WEEKLY:
        iso = now.isocalendar()
        return f"W{iso[0]}-{iso[1]}"
    return now.strftime("%Y-%m-%d")


def get_daily_template(daily_level_id: int) -> Optional[dict]:
    row = get_config_entry(DAILY_TEMPLATE_CATEGORY, str(daily_level_id))
    if row is None:
        return None
    data = row.data
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (ValueError, TypeError):
            return None
    return data


def list_daily_templates() -> list[dict]:
    rows = list_config_entries(DAILY_TEMPLATE_CATEGORY)
    result = []
    for r in rows:
        data = r.data
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (ValueError, TypeError):
                continue
        if isinstance(data, dict):
            result.append(data)
    return result


def daily_level_for_stage(stage_id: int) -> Optional[int]:
    for tpl in list_daily_templates():
        for pair in tpl.get("expedition_and_lv_limit_list") or []:
            if pair and len(pair) >= 1 and int(pair[0]) == stage_id:
                return int(tpl["id"])
    return None


def get_daily_level_count(commander_id: int, daily_level_id: int) -> int:
    key = _current_reset_key(daily_level_id)
    with get_sync_session() as session:
        row = session.execute(
            text(
                "SELECT count FROM commander_daily_level_states "
                "WHERE commander_id = :cid AND daily_level_id = :did"
            ),
            {"cid": commander_id, "did": daily_level_id},
        ).first()
        if row is None:
            return 0
        return int(row[0]) if row[0] is not None else 0


def get_daily_level_counts(commander_id: int) -> dict[int, int]:
    result: dict[int, int] = {}
    with get_sync_session() as session:
        rows = session.execute(
            text(
                "SELECT daily_level_id, count, reset_key FROM commander_daily_level_states "
                "WHERE commander_id = :cid"
            ),
            {"cid": commander_id},
        ).fetchall()
    for daily_level_id, count, reset_key in rows:
        if reset_key != _current_reset_key(int(daily_level_id)):
            continue
        result[int(daily_level_id)] = int(count) if count is not None else 0
    return result


def increment_daily_level_count(commander_id: int, daily_level_id: int, amount: int) -> None:
    if amount <= 0:
        return
    key = _current_reset_key(daily_level_id)
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_daily_level_states
                    (commander_id, daily_level_id, count, reset_key)
                VALUES (:cid, :did, :amount, :key)
                ON CONFLICT (commander_id, daily_level_id)
                DO UPDATE SET
                    count = CASE
                        WHEN commander_daily_level_states.reset_key = EXCLUDED.reset_key
                            THEN commander_daily_level_states.count + EXCLUDED.count
                        ELSE EXCLUDED.count
                    END,
                    reset_key = EXCLUDED.reset_key,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {"cid": commander_id, "did": daily_level_id, "amount": amount, "key": key},
        )
        session.commit()


def apply_daily_level_battle(commander_id: int, stage_id: int) -> Optional[int]:
    daily_level_id = daily_level_for_stage(stage_id)
    if daily_level_id is None:
        return None
    increment_daily_level_count(commander_id, daily_level_id, 1)
    return daily_level_id


def add_daily_quick_stage(commander_id: int, stage_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_daily_quick_stages (commander_id, stage_id)
                VALUES (:cid, :sid)
                ON CONFLICT DO NOTHING
            """),
            {"cid": commander_id, "sid": stage_id},
        )
        session.commit()


def list_daily_quick_stages(commander_id: int) -> list[int]:
    with get_sync_session() as session:
        rows = session.execute(
            text(
                "SELECT stage_id FROM commander_daily_quick_stages "
                "WHERE commander_id = :cid"
            ),
            {"cid": commander_id},
        ).fetchall()
    return [int(r[0]) for r in rows if r[0] is not None]
