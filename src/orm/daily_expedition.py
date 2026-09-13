from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import text

from src.db.session import get_sync_session
from src.orm.config_entry import get_config_entry

MAP_TYPE_SCENARIO = 1
MAP_TYPE_ELITE = 2
MAP_TYPE_EVENT = 3
MAP_TYPE_ACTIVITY_EASY = 4
MAP_TYPE_ACTIVITY_HARD = 5
MAP_TYPE_ACT_EXTRA = 8
MAP_TYPE_ESCORT = 9
MAP_TYPE_SKIRMISH = 10

MAP_DATA_BY_MAP_CATEGORY = "ShareCfg/expedition_data_by_map.json"
CHAPTER_TEMPLATE_CATEGORY = "sharecfgdata/chapter_template.json"

_COUNTER_ELITE = "elite"
_COUNTER_ESCORT = "escort"
_COUNTER_CHAPTER = "chapter"




def _region_location():
    try:
        from src.shopreset.framework import _current_region_location
        return _current_region_location()
    except Exception:
        from datetime import timezone
        return timezone.utc


def _current_reset_key() -> str:
    now = datetime.now(_region_location())
    return now.strftime("%Y-%m-%d")


def _entry_data(row) -> Optional[dict]:
    if row is None:
        return None
    data = row.data
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (ValueError, TypeError):
            return None
    if isinstance(data, (bytes, bytearray)):
        try:
            return json.loads(data.decode("utf-8"))
        except (ValueError, TypeError):
            return None
    return data


def get_map_type(map_id: int) -> int:
    row = get_config_entry(MAP_DATA_BY_MAP_CATEGORY, str(map_id))
    entry = _entry_data(row)
    if entry is None:
        return 0
    try:
        return int(entry.get("type", 0))
    except (ValueError, TypeError):
        return 0


def get_chapter_map_type(chapter_id: int, loop_flag: int = 0) -> int:
    row = get_config_entry(CHAPTER_TEMPLATE_CATEGORY, str(chapter_id))
    entry = _entry_data(row)
    if entry is None:
        return 0
    map_id = entry.get("map", 0)
    if loop_flag:
        loop = _entry_data(get_config_entry("sharecfgdata/chapter_template_loop.json", str(chapter_id)))
        if loop is not None:
            map_id = loop.get("map", map_id)
    try:
        map_id = int(map_id)
    except (ValueError, TypeError):
        return 0
    if map_id == 0:
        return 0
    return get_map_type(map_id)


def chapter_tries_limit(chapter_id: int) -> bool:
    row = get_config_entry(CHAPTER_TEMPLATE_CATEGORY, str(chapter_id))
    entry = _entry_data(row)
    if entry is None:
        return False
    try:
        return int(entry.get("count", 0)) > 0
    except (ValueError, TypeError):
        return False


def _increment(commander_id: int, counter_type: str, entity_id: int, amount: int = 1) -> None:
    if amount <= 0:
        return
    key = _current_reset_key()
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_daily_expedition_states
                    (commander_id, counter_type, entity_id, count, reset_key)
                VALUES (:cid, :ctype, :eid, :amount, :key)
                ON CONFLICT (commander_id, counter_type, entity_id)
                DO UPDATE SET
                    count = CASE
                        WHEN commander_daily_expedition_states.reset_key = EXCLUDED.reset_key
                            THEN commander_daily_expedition_states.count + EXCLUDED.count
                        ELSE EXCLUDED.count
                    END,
                    reset_key = EXCLUDED.reset_key,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {"cid": commander_id, "ctype": counter_type, "eid": entity_id,
             "amount": amount, "key": key},
        )
        session.commit()


def _get_count(commander_id: int, counter_type: str, entity_id: int = 0) -> int:
    key = _current_reset_key()
    with get_sync_session() as session:
        row = session.execute(
            text(
                "SELECT count, reset_key FROM commander_daily_expedition_states "
                "WHERE commander_id = :cid AND counter_type = :ctype AND entity_id = :eid"
            ),
            {"cid": commander_id, "ctype": counter_type, "eid": entity_id},
        ).first()
    if row is None:
        return 0
    if row[0] is None:
        return 0
    if row[1] != key:
        return 0
    return int(row[0])


def increment_elite_expedition_count(commander_id: int) -> None:
    _increment(commander_id, _COUNTER_ELITE, 0, 1)


def get_elite_expedition_count(commander_id: int) -> int:
    return _get_count(commander_id, _COUNTER_ELITE, 0)


def increment_escort_expedition_count(commander_id: int) -> None:
    _increment(commander_id, _COUNTER_ESCORT, 0, 1)


def get_escort_expedition_count(commander_id: int) -> int:
    return _get_count(commander_id, _COUNTER_ESCORT, 0)


def increment_chapter_defeat_count(commander_id: int, chapter_id: int) -> None:
    _increment(commander_id, _COUNTER_CHAPTER, chapter_id, 1)


def get_chapter_defeat_counts(commander_id: int) -> dict[int, int]:
    key = _current_reset_key()
    result: dict[int, int] = {}
    with get_sync_session() as session:
        rows = session.execute(
            text(
                "SELECT entity_id, count, reset_key FROM commander_daily_expedition_states "
                "WHERE commander_id = :cid AND counter_type = :ctype"
            ),
            {"cid": commander_id, "ctype": _COUNTER_CHAPTER},
        ).fetchall()
    for entity_id, count, reset_key in rows:
        if reset_key != key:
            continue
        result[int(entity_id)] = int(count) if count is not None else 0
    return result
