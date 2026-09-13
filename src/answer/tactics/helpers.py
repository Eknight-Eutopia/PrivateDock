import json
import math
from typing import Optional

from src.db.store import get_default_store
from src.orm.config_entry import afetch_config_entries_data, afetch_config_entry_data

# Exp required to advance FROM the given level to the next level.
# Mirrors the client's pg.base.skill_need_exp table (sharecfg/skill_need_exp.lua).
SKILL_NEED_EXP = {
    1: 100,
    2: 200,
    3: 400,
    4: 800,
    5: 1400,
    6: 2200,
    7: 3200,
    8: 4400,
    9: 5800,
    10: 0,
}
DEFAULT_SKILL_MAX_LEVEL = 10
LESSON_ITEM_TYPE = 10
LESSON_ITEM_USAGE = "usage_book"


get_config_entry = afetch_config_entry_data
list_config_entries = afetch_config_entries_data


def decode_uint32_array(raw) -> list:
    if raw is None or raw == "" or raw == b"":
        return []
    if isinstance(raw, list):
        return [int(x) for x in raw]
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, (bytes, bytearray)):
        raw = json.loads(raw.decode("utf-8"))
    if not isinstance(raw, list):
        return []
    result = []
    for value in raw:
        if isinstance(value, (int, float)):
            v = int(value)
            if v >= 0:
                result.append(v)
    return result


async def load_lesson_item_config(item_id: int) -> Optional[tuple]:
    entry = await get_config_entry("sharecfgdata/item_data_statistics.json", str(item_id))
    if entry is None:
        return None
    item_type = entry.get("type", 0)
    usage = entry.get("usage", "")
    usage_arg = decode_uint32_array(entry.get("usage_arg"))
    return item_type, usage, usage_arg


def lesson_exp_from_usage_arg(usage_arg: list, skill_type: int) -> tuple:
    if len(usage_arg) < 4:
        return 0, 0
    duration = usage_arg[0]
    base_exp = usage_arg[1]
    target_skill_type = usage_arg[2]
    bonus_pct = usage_arg[3]
    if duration == 0 or base_exp == 0:
        return 0, 0
    if target_skill_type != 0 and target_skill_type == skill_type:
        exp = int(math.floor(base_exp * (100 + bonus_pct) / 100.0))
    else:
        exp = base_exp
    return duration, exp


async def load_ship_skill_by_pos(ship_template_id: int, skill_pos: int) -> Optional[int]:
    entry = await get_config_entry("sharecfgdata/ship_data_template.json", str(ship_template_id))
    if entry is None:
        return None
    buff_list = decode_uint32_array(entry.get("buff_list_display"))
    if skill_pos == 0 or skill_pos not in buff_list:
        return None
    return skill_pos


async def load_skill_template(skill_id: int) -> Optional[dict]:
    entry = await get_config_entry("ShareCfg/skill_data_template.json", str(skill_id))
    if entry is None:
        return None
    if entry.get("max_level", 0) == 0:
        entry["max_level"] = DEFAULT_SKILL_MAX_LEVEL
    return entry


def calc_granted_lesson_exp(now_unix: int, start_unix: int, finish_unix: int, total_exp: int) -> int:
    if total_exp == 0:
        return 0
    if now_unix <= start_unix:
        return 0
    if now_unix >= finish_unix:
        return total_exp
    duration = finish_unix - start_unix
    if duration == 0:
        return total_exp
    elapsed = now_unix - start_unix
    return int((total_exp * elapsed) / duration)


def apply_lesson_exp(skill: dict, amount: int, max_level: int) -> int:
    if amount == 0 or skill.get("level", 0) >= max_level:
        return 0
    level = skill["level"]
    remaining = amount + skill.get("exp", 0)
    while level < max_level and SKILL_NEED_EXP.get(level, 0) <= remaining:
        remaining -= SKILL_NEED_EXP[level]
        level += 1
    if level >= max_level:
        level = max_level
        remaining = 0
    skill["level"] = level
    skill["exp"] = remaining
    return amount


async def get_commander_skill_class_by_room(commander_id: int, room_id: int) -> Optional[dict]:
    store = get_default_store()
    if store is None:
        return None
    row = await store.afetchrow(
        "SELECT commander_id, room_id, ship_id, skill_pos, skill_id, start_time, finish_time, exp "
        "FROM commander_skill_classes "
        "WHERE commander_id = $1 AND room_id = $2",
        commander_id, room_id
    )
    if row is None:
        return None
    return {
        "commander_id": row[0],
        "room_id": row[1],
        "ship_id": row[2],
        "skill_pos": row[3],
        "skill_id": row[4],
        "start_time": row[5],
        "finish_time": row[6],
        "exp": row[7],
    }


async def create_commander_skill_class(commander_id: int, room_id: int, ship_id: int, skill_pos: int, skill_id: int, start_time: int, finish_time: int, exp: int) -> Optional[Exception]:
    store = get_default_store()
    if store is None:
        return Exception("DB not initialized")
    try:
        await store.aexecute(
            "INSERT INTO commander_skill_classes (commander_id, room_id, ship_id, skill_pos, skill_id, start_time, finish_time, exp) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            commander_id, room_id, ship_id, skill_pos, skill_id, start_time, finish_time, exp
        )
        return None
    except Exception as e:
        return e


async def delete_commander_skill_class(commander_id: int, room_id: int) -> Optional[Exception]:
    store = get_default_store()
    if store is None:
        return Exception("DB not initialized")
    result = await store.aexecute(
        "DELETE FROM commander_skill_classes WHERE commander_id = $1 AND room_id = $2",
        commander_id, room_id
    )
    if result == "0":
        from src.db.store import NotFoundError
        return NotFoundError("skill class not found")
    return None


async def get_or_create_commander_ship_skill(commander_id: int, ship_id: int, skill_pos: int, skill_id: int) -> Optional[dict]:
    store = get_default_store()
    if store is None:
        return None
    await store.aexecute(
        "INSERT INTO commander_ship_skills (commander_id, ship_id, skill_pos, skill_id, level, exp) "
        "VALUES ($1, $2, $3, $4, 1, 0) "
        "ON CONFLICT (commander_id, ship_id, skill_pos) DO NOTHING",
        commander_id, ship_id, skill_pos, skill_id
    )
    row = await store.afetchrow(
        "SELECT commander_id, ship_id, skill_pos, skill_id, level, exp "
        "FROM commander_ship_skills "
        "WHERE commander_id = $1 AND ship_id = $2 AND skill_pos = $3",
        commander_id, ship_id, skill_pos
    )
    if row is None:
        return None
    skill = {
        "commander_id": row[0],
        "ship_id": row[1],
        "skill_pos": row[2],
        "skill_id": row[3],
        "level": row[4],
        "exp": row[5],
    }
    if skill["skill_id"] == 0:
        skill["skill_id"] = skill_id
    return skill


async def save_commander_ship_skill(skill: dict) -> Optional[Exception]:
    store = get_default_store()
    if store is None:
        return Exception("DB not initialized")
    result = await store.aexecute(
        "UPDATE commander_ship_skills SET skill_id = $4, level = $5, exp = $6 "
        "WHERE commander_id = $1 AND ship_id = $2 AND skill_pos = $3",
        skill["commander_id"], skill["ship_id"], skill["skill_pos"],
        skill["skill_id"], skill["level"], skill["exp"]
    )
    if result == "0":
        from src.db.store import NotFoundError
        return NotFoundError("ship skill not found")
    return None


from src.orm.commander_tactics_quick_finish import (
    aget_commander_daily_quick_finish_used as get_commander_daily_quick_finish_used,
    aconsume_commander_quick_finish as consume_commander_quick_finish,
)
from src.orm.commander_buff import alist_active_commander_buff_ids


async def get_commander_skill_learn_time_allowance(commander_id: int, now_unix: int) -> int:
    import datetime
    now_dt = datetime.datetime.fromtimestamp(now_unix, tz=datetime.timezone.utc)
    buff_ids = await alist_active_commander_buff_ids(commander_id, now_dt)
    if not buff_ids:
        return 0
    allowance = 0
    for buff_id in buff_ids:
        entry = await get_config_entry("ShareCfg/benefit_buff_template.json", str(buff_id))
        if entry is None:
            continue
        if entry.get("benefit_type") != "skill_learn_time":
            continue
        effect = entry.get("benefit_effect")
        if effect is None:
            continue
        effect_val = 0
        if isinstance(effect, (int, float)):
            effect_val = int(effect)
        elif isinstance(effect, str):
            try:
                effect_val = int(effect)
            except (ValueError, TypeError):
                continue
        if effect_val > allowance:
            allowance = effect_val
    return allowance
