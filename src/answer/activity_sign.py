"""Shared helpers for 7dayslogin (type 3) and monthsign (type 6) activity claims.

The client auto-opens the sign-in window when its local state says a claim
is available (Activity.readyToAchieve / ActivityProxy.findNextAutoActivity)
and sends CS_11202. The server must grant the day reward, persist the claimed
state (activity_store_states), and echo the persisted state back in SC_11200
so the window does not re-open on the next login.
"""

import json
from datetime import datetime
from typing import Optional

from src.db.store import get_default_store
from src.orm.config_entry import get_config_entry
from src.protobuf import protobuf
from src.shopreset.framework import _current_region_location

# Region-aware "today" used by the client: STimeDescS(GetServerTime(), "*t")
def _region_date(now_unix: int) -> tuple:
    loc = _current_region_location()
    dt = datetime.fromtimestamp(now_unix, tz=loc)
    return dt.year, dt.month, dt.day


def is_same_day(ts_a: int, ts_b: int) -> bool:
    if not ts_a or not ts_b:
        return False
    a = _region_date(ts_a)
    b = _region_date(ts_b)
    return a == b


def current_month_id(now_unix: int) -> tuple:
    year, month, _ = _region_date(now_unix)
    return year, month


def current_day(now_unix: int) -> int:
    _, _, day = _region_date(now_unix)
    return day


def _now_unix() -> int:
    import time
    return int(time.time())


def load_json_entry(category: str, key) -> Optional[dict]:
    try:
        entry = get_config_entry(category, str(key))
    except Exception:
        return None
    if entry is None:
        return None
    data = entry.data if hasattr(entry, "data") else entry
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(data, dict):
        return data
    return None


def load_7day_config(config_id: int) -> Optional[dict]:
    return load_json_entry("ShareCfg/activity_7_day_sign.json", config_id)


def load_month_sign_config(month: int) -> Optional[dict]:
    return load_json_entry("ShareCfg/activity_month_sign.json", month)


# ── store state ──

def load_store_state(commander_id: int, activity_id: int):
    store = get_default_store()
    if store is None:
        return None
    try:
        row = store.fetchrow(
            "SELECT data1, data2, data3, data1_list FROM activity_store_states "
            "WHERE commander_id = $1 AND activity_id = $2",
            commander_id, activity_id,
        )
    except Exception:
        return None
    if not row:
        return None
    return {
        "data1": row[0] or 0,
        "data2": row[1] or 0,
        "data3": row[2] or 0,
        "data1_list": _parse_day_list(row[3]),
    }


def save_store_state(
    commander_id: int,
    activity_id: int,
    data1: int = 0,
    data2: int = 0,
    data3: int = 0,
    day_list: list = None,
    str_data1: str = "",
) -> None:
    store = get_default_store()
    if store is None:
        return
    day_list_json = json.dumps(day_list or [], separators=(",", ":"))
    store.execute(
        "INSERT INTO activity_store_states "
        "(commander_id, activity_id, data1, data2, data3, data1_list, str_data1, created_at, updated_at) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW()) "
        "ON CONFLICT (commander_id, activity_id) DO UPDATE SET "
        "data1 = $3, data2 = $4, data3 = $5, data1_list = $6, str_data1 = $7, updated_at = NOW()",
        commander_id, activity_id, data1, data2, data3, day_list_json, str_data1,
    )


def _parse_day_list(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return [int(x) for x in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [int(x) for x in parsed]
        except (json.JSONDecodeError, TypeError):
            return []
    return []


# ── drop grant ──

def _grant_drop(commander_id: int, drop_type: int, drop_id: int, drop_count: int) -> None:
    store = get_default_store()
    if store is None:
        return
    from src.orm.item import add_item
    from src.orm.owned_equipment import add_owned_equipment
    from src.orm.owned_ship import add_ship
    from src.orm.owned_skin import give_skin
    from src.orm.resource import add_resource
    from src.orm.commander_furniture import add_commander_furniture
    import time

    if drop_type in (14, 15, 31):
        from src.orm.commander_attire import grant_commander_attire_drop_sync
        grant_commander_attire_drop_sync(commander_id, drop_type, drop_id, drop_count)
    elif drop_type == 1:
        add_resource(commander_id, drop_id, drop_count)
    elif drop_type == 2:
        add_item(commander_id, drop_id, drop_count)
    elif drop_type == 3:
        add_owned_equipment(commander_id, drop_id, drop_count)
    elif drop_type == 4:
        for _ in range(drop_count):
            add_ship(commander_id, drop_id)
    elif drop_type == 5:
        add_commander_furniture(commander_id, drop_id, drop_count, int(time.time()))
    elif drop_type == 7:
        for _ in range(drop_count):
            give_skin(commander_id, drop_id)


def grant_drop_list(commander_id: int, drop_list: list) -> list:
    """Apply each [type, id, count] drop and return DROPINFO protobuf entries."""
    result = []
    for drop in drop_list or []:
        if not isinstance(drop, list) or len(drop) < 3:
            continue
        drop_type = int(drop[0])
        drop_id = int(drop[1])
        drop_count = int(drop[2])
        try:
            _grant_drop(commander_id, drop_type, drop_id, drop_count)
        except Exception:
            continue
        result.append(protobuf.DROPINFO(type=drop_type, id=drop_id, number=drop_count))
    return result


def parse_day_drop(config: dict, day: int) -> list:
    """Return the drop list for monthsign config day N: config['day<day>']."""
    key = "day" + str(day)
    raw = config.get(key) if isinstance(config, dict) else None
    if not raw:
        return []
    return raw
