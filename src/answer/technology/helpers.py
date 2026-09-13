import json
import random
from typing import Optional, Tuple

from src.db.store import get_default_store
from src.orm.config_entry import fetch_config_entries_data, fetch_config_entry_data
from src.region.region import local_now

TECHNOLOGY_DATA_TEMPLATE_CATEGORY = "ShareCfg/technology_data_template.json"
CATCHUP_TEMPLATE_CATEGORY = "ShareCfg/technology_catchup_template.json"
SHIP_DATA_BLUEPRINT_CATEGORY = "ShareCfg/ship_data_blueprint.json"

TECHNOLOGY_OK = 0
TECHNOLOGY_INVALID = 1
TECHNOLOGY_PERSIST = 2


get_config_entry = fetch_config_entry_data
list_config_entries = fetch_config_entries_data


def get_or_create_technology_research_state(commander_id: int) -> dict:
    state = _load_technology_research_state(commander_id)
    if state is not None:
        return state
    pools = build_technology_refresh_pools(0)
    state = {
        "commander_id": commander_id,
        "refresh_flag": 0,
        "refresh_day": current_technology_day(),
        "catchup_version": 0,
        "catchup_target": 0,
        "catchup_counters": {},
        "refresh_pools": pools,
        "queue": [],
    }
    _save_technology_research_state(state)
    loaded = _load_technology_research_state(commander_id)
    if loaded is not None:
        return loaded
    return state


def get_or_create_technology_research_state_for_update(commander_id: int) -> dict:
    return get_or_create_technology_research_state(commander_id)


def _load_technology_research_state(commander_id: int) -> Optional[dict]:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT refresh_flag, refresh_day, catchup_version, catchup_target, refresh_pools::text, queue::text, catchup_counters::text "
        "FROM technology_research_states WHERE commander_id = $1",
        commander_id
    )
    if row is None:
        return None
    state = {
        "commander_id": commander_id,
        "refresh_flag": int(row[0]),
        "refresh_day": int(row[1]),
        "catchup_version": int(row[2]),
        "catchup_target": int(row[3]),
        "refresh_pools": json.loads(row[4]) if row[4] else [],
        "queue": json.loads(row[5]) if row[5] else [],
        "catchup_counters": json.loads(row[6]) if row[6] else {},
    }
    if state["refresh_pools"] is None:
        state["refresh_pools"] = []
    if state["queue"] is None:
        state["queue"] = []
    if not isinstance(state["catchup_counters"], dict):
        state["catchup_counters"] = {}
    return state


def _save_technology_research_state(state: dict) -> None:
    store = get_default_store()
    pools_raw = json.dumps(state.get("refresh_pools", []))
    queue_raw = json.dumps(state.get("queue", []))
    counters_raw = json.dumps(state.get("catchup_counters", {}) or {})
    store.execute(
        "INSERT INTO technology_research_states (commander_id, refresh_flag, refresh_day, catchup_version, catchup_target, refresh_pools, queue, catchup_counters, created_at, updated_at) "
        "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, NOW(), NOW()) "
        "ON CONFLICT (commander_id) DO UPDATE SET "
        "refresh_flag = EXCLUDED.refresh_flag, refresh_day = EXCLUDED.refresh_day, "
        "catchup_version = EXCLUDED.catchup_version, catchup_target = EXCLUDED.catchup_target, "
        "refresh_pools = EXCLUDED.refresh_pools, queue = EXCLUDED.queue, "
        "catchup_counters = EXCLUDED.catchup_counters, updated_at = NOW()",
        state["commander_id"], state["refresh_flag"], state["refresh_day"],
        state["catchup_version"], state["catchup_target"], pools_raw, queue_raw, counters_raw
    )


def save_catchup_counters(commander_id: int, counters: dict) -> None:
    store = get_default_store()
    store.execute(
        "UPDATE technology_research_states SET catchup_counters = $2::jsonb, updated_at = NOW() WHERE commander_id = $1",
        commander_id, json.dumps(counters or {})
    )


def current_technology_day() -> int:
    local = local_now()
    return local.year * 10000 + local.month * 100 + local.day


def normalize_technology_refresh_flag(state: dict) -> bool:
    day = current_technology_day()
    if state.get("refresh_day") == day:
        return False
    state["refresh_day"] = day
    state["refresh_flag"] = 0
    return True


def has_active_technology(state: dict, now_unix: int) -> bool:
    for pool in state.get("refresh_pools", []):
        for project in pool.get("technologies", []):
            if project.get("finish_time", 0) > now_unix:
                return True
    return False


def find_technology_pool(state: dict, refresh_id: int) -> Tuple[Optional[dict], bool]:
    for pool in state.get("refresh_pools", []):
        if pool.get("id") == refresh_id:
            return pool, True
    return None, False


def find_technology_project(pool: dict, tech_id: int) -> Tuple[Optional[dict], bool]:
    for project in pool.get("technologies", []):
        if project.get("tech_id") == tech_id:
            return project, True
    return None, False


def build_technology_refresh_pools(seed: int) -> list:
    """Build the offered research set.

    Wiki model: exactly five randomly-chosen available projects, refreshed on
    finish / queue / daily reset. Gated techs (condition != 0) are excluded
    because the EN client model/vo/technology.lua finishCondition() references an
    undefined local when condition != 0 and crashes on open.
    """
    entries = list_config_entries(TECHNOLOGY_DATA_TEMPLATE_CATEGORY)
    if not entries:
        return [{"id": 2, "target": 0, "technologies": [{"tech_id": 1, "finish_time": 0}]}]
    candidates = []
    for entry in entries:
        if entry.get("id", 0) == 0 or entry.get("type", 0) == 0:
            continue
        if entry.get("condition", 0) not in (0, None, ""):
            continue
        candidates.append(entry["id"])
    if len(candidates) <= 5:
        chosen = sorted(candidates)
    else:
        rng = random.Random(seed)
        chosen = sorted(rng.sample(candidates, 5))
    technologies = [{"tech_id": tid, "finish_time": 0} for tid in chosen]
    return [{"id": 2, "target": 0, "technologies": technologies}]


def get_technology_template(tech_id: int) -> dict:
    entry = get_config_entry(TECHNOLOGY_DATA_TEMPLATE_CATEGORY, str(tech_id))
    if entry is None:
        return {"id": tech_id, "type": 1, "time": 60, "condition": 0, "consume": [], "drop_client": [[2, 59001, 1]]}
    return entry


def max_technology_blueprint_version() -> int:
    entries = list_config_entries(TECHNOLOGY_DATA_TEMPLATE_CATEGORY)
    if not entries:
        return 1
    max_version = 0
    for entry in entries:
        version = entry.get("blueprint_version", 0)
        if version > max_version:
            max_version = version
    if max_version == 0:
        return 1
    return max_version


def carry_pool_targets(existing: dict, next_pools: list) -> None:
    target_by_pool = {}
    for pool in existing.get("refresh_pools", []):
        target_by_pool[pool["id"]] = pool.get("target", 0)
    for pool in next_pools:
        if pool["id"] in target_by_pool:
            pool["target"] = target_by_pool[pool["id"]]


def can_consume_technology_cost(commander: any, consume: list) -> bool:
    from src.orm.resource import has_enough_resource
    from src.orm.item import has_enough_item
    for row in consume:
        if len(row) < 3:
            continue
        drop_type = row[0]
        id_val = row[1]
        count = row[2]
        if drop_type == 1:
            if not has_enough_resource(commander.commander_id, id_val, count):
                return False
        elif drop_type == 2:
            if not has_enough_item(commander.commander_id, id_val, count):
                return False
        else:
            return False
    return True


def grant_technology_rewards(commander_id: int, rewards: list) -> None:
    from src.orm.resource import add_resource
    from src.orm.item import add_item
    for reward in rewards:
        if isinstance(reward, dict):
            drop_type = reward.get("type", 0)
            id_val = reward.get("id", 0)
            number = reward.get("number", 0)
        else:
            drop_type = reward[0]
            id_val = reward[1]
            number = reward[2]
        if drop_type == 1:
            add_resource(commander_id, id_val, number)
        else:
            add_item(commander_id, id_val, number)


def consume_technology_cost(commander_id: int, consume: list) -> None:
    from src.orm.resource import consume_resource
    from src.orm.item import consume_item
    for row in consume:
        if len(row) < 3:
            continue
        drop_type = row[0]
        id_val = row[1]
        count = row[2]
        if drop_type == 1:
            consume_resource(commander_id, id_val, count)
        elif drop_type == 2:
            consume_item(commander_id, id_val, count)


def build_drop_info_list(rows: list) -> list:
    result = []
    for row in rows:
        if len(row) < 3:
            continue
        result.append({"type": row[0], "id": row[1], "number": row[2]})
    return result


def is_valid_catchup_target(version: int, target: int) -> bool:
    entries = list_config_entries(CATCHUP_TEMPLATE_CATEGORY)
    if not entries:
        return version == 1 and target == 29901
    for entry in entries:
        if entry.get("id") != version:
            continue
        char_choice = entry.get("char_choice", [])
        return target in char_choice
    return False


def _catchup_template(version: int) -> Optional[dict]:
    entry = get_config_entry(CATCHUP_TEMPLATE_CATEGORY, str(int(version)))
    if entry is None or int(entry.get("id", 0) or 0) != int(version):
        return None
    return entry


def catchup_blueprint_item_id(target: int) -> int:
    """The catch-up bonus always ships the target ship's own PR/DR blueprint
    item (ship_data_blueprint.strengthen_item, e.g. Drake 29904 -> 42022 --
    verified against the official SC_63004 captures)."""
    bp = get_config_entry(SHIP_DATA_BLUEPRINT_CATEGORY, str(int(target)))
    if bp is None:
        return 0
    try:
        return int(bp.get("strengthen_item", 0) or 0)
    except (TypeError, ValueError):
        return 0


def grant_catchup_blueprints(state: dict, count: int = 1) -> list:
    """Catch-up bonus: every completed research project (main flow and research
    queue, verified in the official captures) grants 1 blueprint of the
    selected catch-up ship. Limits per technology_catchup_template: the shared
    counter of a series (`number`) is capped by `obtain_max` (300, split among
    ALL non-UR ships of the series -- the client's addTargetNum bumps every
    non-UR target with the same amount), while a UR/DR ship is capped by
    `obtain_max_per_ur` (150) per ship (`dr_numbers`).

    Updates state["catchup_counters"] in place; the caller persists it via
    save_catchup_counters. Returns granted DROPINFO dicts ([] when no target
    is selected, the config is missing or the cap is already reached)."""
    version = int(state.get("catchup_version", 0) or 0)
    target = int(state.get("catchup_target", 0) or 0)
    if version == 0 or target == 0 or count <= 0:
        return []
    cfg = _catchup_template(version)
    if cfg is None:
        return []
    char_choice = [int(c) for c in (cfg.get("char_choice") or [])]
    if target not in char_choice:
        return []
    ur_chars = {int(c) for c in (cfg.get("ur_char") or [])}
    item_id = catchup_blueprint_item_id(target)
    if item_id <= 0:
        return []

    # NOTE: no `or {}` here -- an existing empty dict is falsy and would be
    # swapped for a fresh object, losing all counter updates.
    counters = state.get("catchup_counters")
    if not isinstance(counters, dict):
        counters = {}
        state["catchup_counters"] = counters
    ssr_by_version = counters.setdefault("ssr", {})
    dr_by_version = counters.setdefault("dr", {})
    key = str(version)

    granted = []
    for _ in range(count):
        if target in ur_chars:
            cap = int(cfg.get("obtain_max_per_ur", 0) or 0)
            if cap <= 0:
                break
            per_ship = dr_by_version.setdefault(key, {})
            current = int(per_ship.get(str(target), 0) or 0)
            if current >= cap:
                break
            per_ship[str(target)] = current + 1
        else:
            cap = int(cfg.get("obtain_max", 0) or 0)
            if cap <= 0:
                break
            current = int(ssr_by_version.get(key, 0) or 0)
            if current >= cap:
                break
            ssr_by_version[key] = current + 1
        granted.append({"type": 2, "id": item_id, "number": 1})
    return granted
