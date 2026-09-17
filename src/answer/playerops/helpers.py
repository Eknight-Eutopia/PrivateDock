import asyncio
import json
from typing import Optional

from src.db.store import get_default_store
from src.logger.logger import log_event, LOG_LEVEL_ERROR
from src.orm.config_entry import (
    fetch_config_entries_data,
    fetch_config_entry_data,
    upsert_config_entry_data,
)
from src.consts.attire import (
    ATTIRE_TYPE_CHAT_FRAME,
    ATTIRE_TYPE_COMBAT_UI,
    ATTIRE_TYPE_ICON_FRAME,
)
from src.protobuf import protobuf

OIL_RESOURCE_ID = 2
COIN_RESOURCE_ID = 1
# Pending oil/gold well output lives in these resource ids (client ResOilField=5,
# ResGoldField=7). The player must CLAIM them (CS_11011/HarvestResourceCommand ->
# handle_give_resources) to move them into the real oil(2)/gold(1) pools. The
# accrual below must credit these PENDING ids, never the actual ones, otherwise
# the wells pay out automatically with no manual collect.
PENDING_OIL_RESOURCE_ID = 5
PENDING_GOLD_RESOURCE_ID = 7

NAVAL_ACADEMY_RUNTIME_CATEGORY = "Runtime/naval_academy_runtime.json"

from src.orm.morale import (
    MORALE_TICK_SECONDS,
    SHIP_STATE_DORM_REST,
    SHIP_STATE_DORM_TRAINING,
    SHIP_STATE_ONSEN,
    apply_commander_morale_recovery,
    get_active_event_count,
    is_dorm_ship_state,
    morale_recovery_profile,
)


def get_config_entry(category: str, key: str) -> Optional[dict]:
    """Fail-soft read: a broken row degrades to "no config", never to a crash.

    These run on login and on the periodic well-accrual path, so an unreadable
    entry must not take the handler down. The error is logged rather than
    swallowed silently.
    """
    try:
        return fetch_config_entry_data(category, key)
    except Exception as e:
        log_event("PlayerOps", "ConfigRead",
                  f"config entry {category}/{key} unreadable: {e}", LOG_LEVEL_ERROR)
        return None


def list_config_entries(category: str) -> list:
    """Fail-soft variant of :func:`fetch_config_entries_data` (see above)."""
    try:
        return fetch_config_entries_data(category)
    except Exception as e:
        log_event("PlayerOps", "ConfigRead",
                  f"config category {category} unreadable: {e}", LOG_LEVEL_ERROR)
        return []


def load_naval_academy_runtime(commander_id: int) -> Optional[dict]:
    entry = get_config_entry(NAVAL_ACADEMY_RUNTIME_CATEGORY, str(commander_id))
    if entry is None:
        return None
    entry["commander_id"] = commander_id
    return entry


def load_or_create_naval_academy_runtime(commander_id: int) -> dict:
    runtime = load_naval_academy_runtime(commander_id)
    if runtime is not None:
        return runtime
    return {
        "commander_id": commander_id,
        "oil_well_level": 1,
        "gold_well_level": 1,
        "oil_collect_timestamp": 0,
        "gold_collect_timestamp": 0,
        "oil_upgrade_start_time": 0,
        "oil_upgrade_complete_time": 0,
        "gold_upgrade_start_time": 0,
        "gold_upgrade_complete_time": 0,
    }


def save_naval_academy_runtime(runtime: dict) -> None:
    upsert_config_entry_data(
        NAVAL_ACADEMY_RUNTIME_CATEGORY, runtime["commander_id"], runtime
    )


def _load_level_templates(category: str) -> dict:
    by_level = {}
    max_level = 0
    for entry in list_config_entries(category):
        level = entry.get("level", 0)
        if level == 0:
            continue
        by_level[level] = entry
        if level > max_level:
            max_level = level
    if max_level == 0:
        max_level = 1
        by_level[1] = {"level": 1, "hour_time": 1}
    return {"by_level": by_level, "max_level": max_level}


def load_academy_runtime_templates():
    # Canteen (oil well) = ShareCfg/oilfield_template.json; Merchant (gold well,
    # client GoldResourceField) = ShareCfg/tradingport_template.json. These are
    # different tables -- the merchant pays ~3x more per level.
    oil = _load_level_templates("ShareCfg/oilfield_template.json")
    coin = _load_level_templates("ShareCfg/tradingport_template.json")
    return {
        "oil_by_level": oil["by_level"],
        "oil_max_level": oil["max_level"],
        "coin_by_level": coin["by_level"],
        "coin_max_level": coin["max_level"],
        "max_level": max(oil["max_level"], coin["max_level"]),
    }


def clamp_academy_level(level: int, max_level: int, changed: bool):
    if level == 0:
        return 1, True
    if level > max_level:
        return max_level, True
    return level, changed


def finalize_upgrade_if_done(level, finish, max_level, now_unix, changed):
    if finish == 0 or finish > now_unix:
        return changed
    if level < max_level:
        level = level + 1
        changed = True
    return changed


def infer_upgrade_start(level: int, finish: int, templates: dict) -> int:
    oil_by_level = templates.get("oil_by_level", {})
    template = oil_by_level.get(level)
    if template is None:
        return 0
    t = template.get("time", 0)
    if t == 0 or finish <= t:
        return 0
    return finish - t


def normalize_naval_academy_runtime(runtime: dict, templates: dict, now_unix: int, baseline: int) -> bool:
    changed = False

    runtime["oil_well_level"], changed = clamp_academy_level(
        runtime.get("oil_well_level", 0), templates.get("oil_max_level", templates["max_level"]), changed)
    runtime["gold_well_level"], changed = clamp_academy_level(
        runtime.get("gold_well_level", 0), templates.get("coin_max_level", templates["max_level"]), changed)

    if runtime.get("oil_collect_timestamp", 0) == 0 and baseline > 0:
        runtime["oil_collect_timestamp"] = baseline
        changed = True
    if runtime.get("gold_collect_timestamp", 0) == 0 and baseline > 0:
        runtime["gold_collect_timestamp"] = baseline
        changed = True

    oil_level = runtime.get("oil_well_level", 1)
    oil_start = runtime.get("oil_upgrade_start_time", 0)
    oil_finish = runtime.get("oil_upgrade_complete_time", 0)
    if oil_finish and oil_finish > 0 and oil_finish <= now_unix:
        if oil_level < templates.get("oil_max_level", templates["max_level"]):
            runtime["oil_well_level"] = oil_level + 1
            runtime["oil_upgrade_start_time"] = 0
            runtime["oil_upgrade_complete_time"] = 0
            changed = True

    gold_level = runtime.get("gold_well_level", 1)
    gold_start = runtime.get("gold_upgrade_start_time", 0)
    gold_finish = runtime.get("gold_upgrade_complete_time", 0)
    if gold_finish and gold_finish > 0 and gold_finish <= now_unix:
        if gold_level < templates.get("coin_max_level", templates["max_level"]):
            runtime["gold_well_level"] = gold_level + 1
            runtime["gold_upgrade_start_time"] = 0
            runtime["gold_upgrade_complete_time"] = 0
            changed = True

    if runtime.get("oil_upgrade_complete_time", 0) > now_unix and runtime.get("oil_upgrade_start_time", 0) == 0:
        inferred = infer_upgrade_start(runtime["oil_well_level"], runtime["oil_upgrade_complete_time"], templates)
        if inferred > 0:
            runtime["oil_upgrade_start_time"] = inferred
            changed = True

    if runtime.get("gold_upgrade_complete_time", 0) > now_unix and runtime.get("gold_upgrade_start_time", 0) == 0:
        inferred = infer_upgrade_start(runtime["gold_well_level"], runtime["gold_upgrade_complete_time"], templates)
        if inferred > 0:
            runtime["gold_upgrade_start_time"] = inferred
            changed = True

    if runtime.get("oil_upgrade_complete_time", 0) > 0 and runtime.get("oil_upgrade_complete_time", 0) <= runtime.get("oil_upgrade_start_time", 0):
        runtime["oil_upgrade_start_time"] = 0
        runtime["oil_upgrade_complete_time"] = 0
        changed = True

    if runtime.get("gold_upgrade_complete_time", 0) > 0 and runtime.get("gold_upgrade_complete_time", 0) <= runtime.get("gold_upgrade_start_time", 0):
        runtime["gold_upgrade_start_time"] = 0
        runtime["gold_upgrade_complete_time"] = 0
        changed = True

    return changed


def compute_facility_accrual(last_collect: int, now_unix: int, upgrade_start: int, upgrade_end: int, template: dict) -> int:
    if last_collect == 0 or last_collect >= now_unix:
        return 0

    # Client formula (ResourceFieldProductAttr / BaseResourceField.getHourProduct):
    # per-hour output = hour_time * production (displayed as "N/h"). The template's
    # production alone is NOT the hourly rate.
    hour_time = template.get("hour_time", 0)
    production = template.get("production", 0)
    store = template.get("store", 0)
    if hour_time == 0 or production == 0 or store == 0:
        return 0
    per_hour = hour_time * production

    active_seconds = now_unix - last_collect
    if upgrade_end > last_collect and upgrade_start < now_unix and upgrade_end > upgrade_start:
        overlap_start = upgrade_start
        if overlap_start < last_collect:
            overlap_start = last_collect
        overlap_end = upgrade_end
        if overlap_end > now_unix:
            overlap_end = now_unix
        if overlap_end > overlap_start:
            active_seconds -= overlap_end - overlap_start

    gain = int((active_seconds * per_hour) / 3600)
    if gain > store:
        return store
    return gain


def _pending_resource_amount(commander_id: int, resource_id: int) -> int:
    """Current uncollected well amount (owned_resources resource_id 5/7).
    The accrual cap needs it: officially the well stops producing once its
    storage (template `store`) is full, so pending may never exceed store."""
    from src.orm.resource import get_resource_amount
    return get_resource_amount(commander_id, resource_id)


def _player_tech_id(commander_id: int, group_id: int) -> int:
    """The player's CURRENT public-tech id in a group (guild_user_technology_states).
    This is the same value SC_60103.user_info.tech_id carries to the client
    (PublicGuild.InitUser), so the clamp and the client's local cap always
    read the same level."""
    row = get_default_store().fetchrow(
        "SELECT tech_id FROM guild_user_technology_states "
        "WHERE commander_id = $1 AND tech_group = $2",
        commander_id, group_id,
    )
    return int(row[0]) if row else 0


def _guild_resource_addition(resource_type: int, commander_id: int | None = None) -> int:
    """Guild-technology addition to the oil/gold bag cap (client player.lua
    getLevelMaxGold/getLevelMaxOil -> baseguild.getMaxGoldAddition ->
    group tech getAddition = the `num` of the tech at the player's CURRENT
    level). The client builds that tech from its own `tech_id` (SC_60103 ->
    PublicGuild.InitUser) and falls back to the group's first tech (num 0)
    when the data has not arrived yet — both states give 0 for an un-upgraded
    group, so reading the player's own row here agrees with the client at
    every point of the session. The shared head in
    public_guild_technology_states is pinned to the max-level tech as a
    display hack and must NOT feed this clamp (2026-09-13: the pinned head's
    num=15000 let CS_11013 grant gold past the client's cap and drain the
    well field)."""
    if commander_id is None:
        return 0
    try:
        from src.answer.guild.public_tech import _tech_map
        techs = _tech_map()
        effect = "gold_max" if resource_type == 1 else "oil_max"
        group = next(
            (d.get("group") for d in techs.values()
             if d.get("effect_args") and d["effect_args"][0] == effect),
            None,
        )
        if group is None:
            return 0
        tech_id = _player_tech_id(commander_id, group)
        if not tech_id:
            return 0
        return int((techs.get(tech_id) or {}).get("num", 0) or 0)
    except Exception:
        return 0


def player_max_resource(resource_type: int, level: int, commander_id: int | None = None) -> Optional[int]:
    """The player's max oil/gold bag capacity (client player.lua
    getLevelMaxOil/getLevelMaxGold -> user_level[level].max_oil/max_gold plus
    the guild technology addition). Returns None when the config is
    unavailable (no cap enforced). Pass ``commander_id`` for the live
    client-consistent cap (see :func:`_guild_resource_addition`)."""
    try:
        level = int(level or 0)
    except (TypeError, ValueError):
        return None
    if level < 1:
        return None
    entry = fetch_config_entry_data("ShareCfg/user_level.json", level)
    if not isinstance(entry, dict):
        return None
    key = "max_gold" if resource_type == 1 else "max_oil"
    try:
        base = int(entry.get(key, 0) or 0)
    except (TypeError, ValueError):
        return None
    if base <= 0:
        return None
    return base + _guild_resource_addition(resource_type, commander_id)


def _apply_well_accrual(runtime: dict, templates: dict, commander_id: int, now_unix: int, changed: bool) -> bool:
    from src.orm.resource import add_resource as _add_resource

    oil_template = templates["oil_by_level"].get(runtime["oil_well_level"])
    if oil_template:
        oil_gain = compute_facility_accrual(
            runtime.get("oil_collect_timestamp", 0),
            now_unix,
            runtime.get("oil_upgrade_start_time", 0),
            runtime.get("oil_upgrade_complete_time", 0),
            oil_template,
        )
        # Original semantics (client pushnotificationmgr.lua compares
        # oilField < store): production stops once the well storage is full;
        # it only resumes after the player collects. Without this cap every
        # academy-screen open / login re-armed the accrual window and pending
        # oil (res 5) grew without bound.
        pending = _pending_resource_amount(commander_id, PENDING_OIL_RESOURCE_ID)
        oil_gain = min(oil_gain, max(0, oil_template.get("store", 0) - pending))
        if oil_gain > 0:
            # Credit the PENDING oil field (res 5); the player collects it via
            # CS_11013 (handle_give_resources), which moves it into real oil(2).
            _add_resource(commander_id, PENDING_OIL_RESOURCE_ID, oil_gain)
            changed = True
        runtime["oil_collect_timestamp"] = now_unix

    coin_template = templates["coin_by_level"].get(runtime["gold_well_level"])
    if coin_template:
        coin_gain = compute_facility_accrual(
            runtime.get("gold_collect_timestamp", 0),
            now_unix,
            runtime.get("gold_upgrade_start_time", 0),
            runtime.get("gold_upgrade_complete_time", 0),
            coin_template,
        )
        pending_gold = _pending_resource_amount(commander_id, PENDING_GOLD_RESOURCE_ID)
        coin_gain = min(coin_gain, max(0, coin_template.get("store", 0) - pending_gold))
        if coin_gain > 0:
            # Credit the PENDING gold field (res 7); collected via CS_11013 into
            # real gold(1).
            _add_resource(commander_id, PENDING_GOLD_RESOURCE_ID, coin_gain)
            changed = True
        runtime["gold_collect_timestamp"] = now_unix
    return changed


def load_naval_academy_runtime_snapshot(commander_id: int, now_unix: int):
    templates = load_academy_runtime_templates()
    runtime = load_or_create_naval_academy_runtime(commander_id)
    changed = normalize_naval_academy_runtime(runtime, templates, now_unix, 0)
    store = get_default_store()
    changed = _apply_well_accrual(runtime, templates, commander_id, now_unix, changed)
    if changed:
        save_naval_academy_runtime(runtime)
    return runtime


def apply_naval_academy_login_catchup(commander_id: int, previous_login_at, now_unix: int) -> None:
    try:
        _apply_naval_academy_login_catchup(commander_id, previous_login_at, now_unix)
    except Exception:
        pass


def _apply_naval_academy_login_catchup(commander_id: int, previous_login_at, now_unix: int) -> None:
    templates = load_academy_runtime_templates()
    runtime = load_or_create_naval_academy_runtime(commander_id)

    baseline = now_unix
    if previous_login_at is not None and previous_login_at > 0:
        baseline = previous_login_at
    if baseline > now_unix:
        baseline = now_unix

    runtime_changed = normalize_naval_academy_runtime(runtime, templates, now_unix, baseline)

    store = get_default_store()
    runtime_changed = _apply_well_accrual(runtime, templates, commander_id, now_unix, runtime_changed)

    if runtime.get("oil_upgrade_complete_time", 0) > 0 and runtime["oil_upgrade_complete_time"] <= now_unix:
        runtime["oil_upgrade_start_time"] = 0
        runtime["oil_upgrade_complete_time"] = 0
        runtime_changed = True

    if runtime.get("gold_upgrade_complete_time", 0) > 0 and runtime["gold_upgrade_complete_time"] <= now_unix:
        runtime["gold_upgrade_start_time"] = 0
        runtime["gold_upgrade_complete_time"] = 0
        runtime_changed = True

    if runtime_changed:
        save_naval_academy_runtime(runtime)


def list_commander_skill_classes(commander_id: int) -> list:
    store = get_default_store()
    rows = store.fetch(
        "SELECT room_id, ship_id, skill_pos, skill_id, start_time, finish_time, exp "
        "FROM commander_skill_classes WHERE commander_id = $1 ORDER BY room_id ASC",
        commander_id
    )
    result = []
    for row in rows:
        result.append({
            "room_id": row[0],
            "ship_id": row[1],
            "skill_pos": row[2],
            "skill_id": row[3],
            "start_time": row[4],
            "finish_time": row[5],
            "exp": row[6],
        })
    return result


from src.orm.commander_tactics_quick_finish import get_commander_daily_quick_finish_used
from src.orm.commander_buff import list_active_commander_buff_ids


def get_commander_skill_learn_time_allowance(commander_id: int, now_unix: int) -> int:
    import datetime
    now_dt = datetime.datetime.fromtimestamp(now_unix, tz=datetime.timezone.utc)
    buff_ids = list_active_commander_buff_ids(commander_id, now_dt)
    if not buff_ids:
        return 0

    allowance = 0
    for buff_id in buff_ids:
        entry = get_config_entry("ShareCfg/benefit_buff_template.json", str(buff_id))
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
        else:
            continue
        if effect_val > allowance:
            allowance = effect_val
    return allowance


def commander_has_attire(commander_id: int, attire_type: int, attire_id: int, now_unix: int) -> bool:
    import datetime
    now_dt = datetime.datetime.fromtimestamp(now_unix, tz=datetime.timezone.utc)
    store = get_default_store()
    row = store.fetchrow(
        "SELECT expires_at FROM commander_attires WHERE commander_id = $1 AND type = $2 AND attire_id = $3",
        commander_id, attire_type, attire_id
    )
    if row is None:
        return False
    expires_at = row[0]
    if expires_at is not None:
        if isinstance(expires_at, str):
            from src.db.sqlite_types import _convert_timestamp
            expires_at = _convert_timestamp(expires_at)
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
        if expires_at is not None and expires_at < now_dt:
            return False
    return True


def get_active_event_count(commander_id: int) -> int:
    store = get_default_store()
    try:
        row = store.fetchrow(
            "SELECT COUNT(*) FROM event_collections WHERE commander_id = $1 AND finish_time > 0",
            commander_id
        )
    except Exception:
        return 0
    if row is None:
        return 0
    return row[0]
