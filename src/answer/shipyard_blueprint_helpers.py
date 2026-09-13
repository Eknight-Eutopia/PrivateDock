from typing import Optional

SHIPYARD_RESULT_OK = 0
SHIPYARD_RESULT_FAILED = 1
SHIPYARD_RESULT_NO_ITEMS = 2
SHIPYARD_COOLDOWN_SECONDS = 86400
SHIPYARD_STRENGTH_RECORD_SLOT = 1

# TechnologyConst.SHIP_LEVEL_FOR_BUFF: a ship group whose best copy reached
# this level contributes fleet_tech pt_level (EN client technologynationproxy).
SHIP_LEVEL_FOR_BUFF = 120

# Task sub-types of the Dev Dock open-condition rows (sharecfgdata task_data_template).
TASK_SUB_TYPE_COLLECT_SHIPS = 1040   # PR1 "register N faction/class ships"
TASK_SUB_TYPE_TECHNOLOGY_POINT = 1050  # PR2+/DR "reach N faction tech points"

_FLEET_TECH_SHIP_TEMPLATES_CACHE = None  # group_id -> fleet_tech_ship_template dict


def _fleet_tech_ship_templates() -> dict:
    """fleet_tech_ship_template configs keyed by ship-group id, cached
    process-wide (config_entries mirror of ShareCfg/fleet_tech_ship_template.json)."""
    global _FLEET_TECH_SHIP_TEMPLATES_CACHE
    if _FLEET_TECH_SHIP_TEMPLATES_CACHE is not None:
        return _FLEET_TECH_SHIP_TEMPLATES_CACHE
    out: dict = {}
    try:
        from src.orm.config_entry import list_config_entries_sync
        entries = list_config_entries_sync("ShareCfg/fleet_tech_ship_template.json")
    except Exception:
        entries = []
    for e in entries:
        d = e.data if isinstance(e.data, dict) else None
        if d is None:
            continue
        try:
            gid = int(d.get("id", 0) or 0)
        except (TypeError, ValueError):
            continue
        if gid:
            out[gid] = d
    _FLEET_TECH_SHIP_TEMPLATES_CACHE = out
    return out


def compute_faction_tech_points(commander_id: int, store=None) -> dict:
    """Faction tech points per nation, mirroring the EN client's
    TechnologyNationProxy:nationPointFilter().

    Every collected ship group listed in fleet_tech_ship_template contributes
    pt_get (the group is owned), plus pt_level when its best copy reached
    SHIP_LEVEL_FOR_BUFF, plus pt_upgrage when its best copy reached the group's
    top star form (>= max_star). The per-group stats (max level, max star) are
    exactly the ones the server sends in SC_17001, so the result agrees with
    the bars the client renders for the Dev Dock sub_type-1050 prerequisites.

    Returns {nation: points}, keyed by the group's nationality (the same Nation
    enum values used as task target_id by the 1050 unlock conditions)."""
    if store is None:
        from src.db.store import get_default_store
        store = get_default_store()
    if store is None:
        return {}
    templates = _fleet_tech_ship_templates()
    if not templates:
        return {}
    points: dict = {}
    try:
        rows = store.fetch(
            "SELECT s.template_id / 10 AS gid, s.nationality, "
            "MAX(o.level) AS lv_max, MAX(s.star) AS star_max "
            "FROM owned_ships o JOIN ships s ON o.ship_id = s.template_id "
            "WHERE o.owner_id = $1 AND o.deleted_at IS NULL "
            "GROUP BY s.template_id / 10, s.nationality",
            commander_id,
        )
    except Exception:
        return {}
    for r in rows:
        try:
            gid = int(r[0])
            nation = int(r[1] or 0)
            lv_max = int(r[2] or 0)
            star_max = int(r[3] or 0)
        except (TypeError, ValueError):
            continue
        t = templates.get(gid)
        if t is None:
            continue
        try:
            pts = int(t.get("pt_get", 0) or 0)
            if lv_max >= SHIP_LEVEL_FOR_BUFF:
                pts += int(t.get("pt_level", 0) or 0)
            if star_max >= int(t.get("max_star", 0) or 0):
                pts += int(t.get("pt_upgrage", 0) or 0)
        except (TypeError, ValueError):
            continue
        points[nation] = points.get(nation, 0) + pts
    return points


def faction_tech_points_for_nation(commander_id: int, nation) -> int:
    """Faction tech points of one nation (nation may be str/int)."""
    try:
        key = int(str(nation))
    except (TypeError, ValueError):
        return 0
    return int(compute_faction_tech_points(commander_id).get(key, 0) or 0)

def ensure_commander_loaded_for_shipyard(commander) -> Optional[Exception]:
    if (getattr(commander, "owned_ships_map", None) is None
            or getattr(commander, "commander_items_map", None) is None
            or getattr(commander, "owned_resources_map", None) is None):
        try:
            commander.load()
        except Exception as e:
            return e
    return None


def _row_to_dict(row) -> Optional[dict]:
    """Normalize an ORM row (or dict) to a plain dict of column values."""
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    cols = getattr(row, "__table__", None)
    if cols is None:
        return None
    return {c.name: getattr(row, c.name) for c in cols.columns}


def _get(entry, key, default=0):
    """Read key from a model row or dict."""
    if entry is None:
        return default
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _set(entry, key, value):
    """Write key into a model row or dict."""
    if isinstance(entry, dict):
        entry[key] = value
    else:
        setattr(entry, key, value)


def list_shipyard_blueprint_proto(commander_id: int) -> list:
    from src.orm.shipyard import list_commander_shipyard_blueprints
    out = []
    for entry in list_commander_shipyard_blueprints(commander_id):
        d = _row_to_dict(entry) or {}
        out.append({
            "id": d.get("blueprint_id", 0),
            "ship_id": d.get("ship_id", 0),
            "start_time": d.get("start_time", 0),
            "blue_print_level": d.get("blue_print_level", 0),
            "exp": d.get("exp", 0),
            "start_duration": d.get("start_duration", 0),
        })
    return out


def get_shipyard_state_or_default(commander_id: int) -> dict:
    from src.orm.shipyard import get_commander_shipyard_state
    from src.db.store import NotFoundError
    try:
        state = get_commander_shipyard_state(commander_id)
    except NotFoundError:
        return {"commander_id": commander_id, "cold_time": 0,
                "daily_catchup_strengthen": 0, "daily_catchup_strengthen_ur": 0}
    return _row_to_dict(state) or {"commander_id": commander_id, "cold_time": 0,
                                   "daily_catchup_strengthen": 0, "daily_catchup_strengthen_ur": 0}


def get_or_init_shipyard_blueprint(commander_id: int, blueprint_id: int):
    """Return the commander's blueprint row, creating a blank one on first touch."""
    from src.orm.shipyard import get_commander_shipyard_blueprint, upsert_commander_shipyard_blueprint
    row = get_commander_shipyard_blueprint(commander_id, blueprint_id)
    if row is None:
        from src.orm.commander_shipyard_blueprint import CommanderShipyardBlueprint
        row = CommanderShipyardBlueprint(
            commander_id=commander_id,
            blueprint_id=blueprint_id,
            ship_id=0,
            start_time=0,
            blue_print_level=0,
            exp=0,
            start_duration=0,
        )
        upsert_commander_shipyard_blueprint(row)
    return row


def is_shipyard_task_satisfied(commander_id: int, task_id: int) -> tuple[bool, Optional[Exception]]:
    """True when the commander holds the task and it is claimed or its progress
    reached the template target. Task templates come from config_entries
    (sharecfgdata/task_data_template.json) -- the old orm mirror tables are not
    populated on either engine.

    sub_type-1050 Dev Dock prerequisites ("reach N faction tech points") have no
    server-pushed progress: the client derives them from its own fleet-tech
    mirror, so here they are satisfied against the live faction points computed
    from the dock (compute_faction_tech_points), matching what the client bar
    shows."""
    from src.orm.commander_task import get_commander_task
    from src.orm.config_entry import get_config_entry_sync
    try:
        task = get_commander_task(commander_id, task_id)
    except Exception as e:
        return False, e
    if task is None:
        return False, None
    if _get(task, "submit_time", 0) != 0:
        return True, None
    try:
        entry = get_config_entry_sync("sharecfgdata/task_data_template.json", str(task_id))
    except Exception:
        entry = None
    template = entry.data if entry is not None else None
    if not isinstance(template, dict):
        return False, None
    try:
        target_num = int(template.get("target_num", 0) or 0)
        sub_type = int(template.get("sub_type", 0) or 0)
    except (TypeError, ValueError):
        return False, None
    if target_num == 0:
        return True, None
    if sub_type == TASK_SUB_TYPE_TECHNOLOGY_POINT:
        nation_points = faction_tech_points_for_nation(commander_id, template.get("target_id", 0))
        return nation_points >= target_num, None
    return int(_get(task, "progress", 0) or 0) >= target_num, None


def _blueprint_task_ids(cfg: dict) -> list:
    """All research/open-condition task ids referenced by a blueprint config.

    unlock_task is a list of [task_id, open_offset_seconds] pairs; the offsets
    must NOT be treated as task ids.
    """
    out = []
    seen = set()
    for entry in cfg.get("unlock_task_open_condition", []):
        tid = int(entry or 0)
        if tid and tid not in seen:
            seen.add(tid)
            out.append(tid)
    for group in cfg.get("unlock_task", []):
        if not isinstance(group, (list, tuple)) or not group:
            continue
        tid = int(group[0] or 0)
        if tid and tid not in seen:
            seen.add(tid)
            out.append(tid)
    return out


def is_blueprint_development_finished(entry, cfg) -> tuple[bool, Optional[Exception]]:
    if entry is None or cfg is None:
        return False, None
    total, err = total_blueprint_levels(cfg)
    if err is not None:
        return False, err
    if int(_get(entry, "blue_print_level", 0) or 0) < total:
        return False, None
    return True, None


def is_shipyard_blueprint_ready_to_finish(commander_id: int, entry, cfg) -> tuple[bool, Optional[Exception]]:
    if entry is None or cfg is None:
        return False, None
    if int(_get(entry, "start_time", 0) or 0) == 0 and int(_get(entry, "start_duration", 0) or 0) == 0:
        return False, None
    finished, err = is_blueprint_development_finished(entry, cfg)
    if err is not None:
        return False, err
    if finished:
        return True, None

    task_ids = _blueprint_task_ids(cfg)
    if not task_ids:
        return False, None
    for task_id in task_ids:
        ok, err = is_shipyard_task_satisfied(commander_id, task_id)
        if err is not None:
            return False, err
        if not ok:
            return False, None
    return True, None


def total_blueprint_levels(cfg: Optional[dict]) -> tuple[int, Optional[Exception]]:
    if cfg is None:
        return 0, Exception("nil blueprint config")
    strengthen_effect = cfg.get("strengthen_effect", [])
    fate_strengthen = cfg.get("fate_strengthen", [])
    return len(strengthen_effect) + len(fate_strengthen), None


def blueprint_strength_id_for_level(cfg: dict, level: int) -> tuple[int, bool]:
    strengthen_effect = cfg.get("strengthen_effect", [])
    fate_strengthen = cfg.get("fate_strengthen", [])
    if level < len(strengthen_effect):
        return strengthen_effect[level], True
    fate_index = level - len(strengthen_effect)
    if fate_index < len(fate_strengthen):
        return fate_strengthen[fate_index], True
    return 0, False


def apply_blueprint_exp_gain(entry, cfg: dict, ship_level: int, gain: int) -> tuple[bool, Optional[Exception]]:
    if gain == 0:
        return False, None
    total_levels, err = total_blueprint_levels(cfg)
    if err is not None:
        return False, err
    if int(_get(entry, "blue_print_level", 0) or 0) >= total_levels:
        return False, None

    remaining = gain
    level = int(_get(entry, "blue_print_level", 0) or 0)
    exp = int(_get(entry, "exp", 0) or 0)

    while remaining > 0 and level < total_levels:
        strength_id, ok = blueprint_strength_id_for_level(cfg, level)
        if not ok:
            return False, None
        from src.orm.config_entry import get_config_entry_sync
        strength_cfg = None
        try:
            e2 = get_config_entry_sync("ShareCfg/ship_strengthen_blueprint.json", str(strength_id))
        except Exception:
            e2 = None
        if e2 is not None and isinstance(e2.data, dict):
            strength_cfg = e2.data
        if strength_cfg is None:
            return False, None
        if ship_level < int(strength_cfg.get("need_lv", 0) or 0):
            return False, None
        need_exp = int(strength_cfg.get("need_exp", 0) or 0)
        if need_exp == 0:
            level += 1
            exp = 0
            continue
        if exp >= need_exp:
            level += 1
            exp = 0
            continue
        need = need_exp - exp
        if remaining >= need:
            remaining -= need
            level += 1
            exp = 0
            continue
        exp += remaining
        remaining = 0

    _set(entry, "blue_print_level", level)
    if level >= total_levels:
        _set(entry, "exp", 0)
    else:
        _set(entry, "exp", exp)
    return True, None


def shipyard_now_unix() -> int:
    import time
    return int(time.time())


# --- Combat Data Collection (dev-chain exp missions, sub_type 1041) ---
#
# The 8 dev missions per PR ship sit in ship_data_blueprint.unlock_task as
# [task_id, open_offset] pairs. Task templates with sub_type 1041
# (TASK_SUB_TYPE_BATTLE_EXP) demand accumulated battle EXP from ships of
# specific (nationality, ship_type) categories (e.g. Neptune needs 1,000,000
# EXP from Royal Navy vanguard ships). The client renders that progress from
# the server-pushed task row, so the server must advance these rows when a
# battle grants EXP -- restricted to the gameplay the wiki lists as supported
# (Campaign/Events/War Archives/Operation Siren/Daily Raids; NOT Exercise,
# dorm or commissions). A mission only accrues once its 24h unlock offset
# (from the development start_time) has passed, matching the client's
# ShipBluePrint.getTaskStateById WAIT gate.

# BATTLE_SYSTEM_* values from battle_session: 1 SCENARIO, 2 ROUTINE,
# 11 SUB (daily raids), 51 WORLD (Operation Siren). DUEL (3) = Exercise.
_COMBAT_DATA_COUNT_SYSTEMS = frozenset({1, 2, 11, 51})

_chain_meta_cache = None          # task_id -> (blueprint_id, open_offset)
_exp_template_cache = None        # task_id -> (frozenset[(nat, type)], target_num)
_statistics_nattype_cache = {}    # template_id -> (nationality, type)


from src.orm.config_entry import entry_data as _entry_data


def _ensure_dev_chain_caches():
    global _chain_meta_cache, _exp_template_cache
    if _chain_meta_cache is not None and _exp_template_cache is not None:
        return
    from src.orm.config_entry import list_config_entries_sync
    chain = {}
    try:
        bps = list_config_entries_sync("ShareCfg/ship_data_blueprint.json")
        for e in bps:
            data = _entry_data(e)
            if data is None:
                continue
            bp_id = data.get("id")
            if bp_id is None:
                continue
            for group in data.get("unlock_task", []):
                if not isinstance(group, (list, tuple)) or not group:
                    continue
                try:
                    tid = int(group[0] or 0)
                    offset = int(group[1] or 0) if len(group) > 1 else 0
                except (TypeError, ValueError):
                    continue
                if tid:
                    chain[tid] = (int(bp_id), offset)
    except Exception:
        pass

    exp_templates = {}
    try:
        tpls = list_config_entries_sync("sharecfgdata/task_data_template.json")
        for e in tpls:
            data = _entry_data(e)
            if data is None:
                continue
            tid = data.get("id")
            if tid is None or int(tid) not in chain:
                continue
            if int(data.get("sub_type", 0) or 0) != 1041:
                continue
            target_num = int(data.get("target_num", 0) or 0)
            if target_num <= 0:
                continue
            pairs = frozenset()
            raw = data.get("target_id")
            if isinstance(raw, list):
                pairs = frozenset(
                    (int(a), int(b))
                    for a, b in raw
                    if isinstance(a, (int, str)) and isinstance(b, (int, str))
                    and str(a).strip() != "" and str(b).strip() != ""
                )
            if pairs:
                exp_templates[int(tid)] = (pairs, target_num)
    except Exception:
        pass

    _chain_meta_cache = chain
    _exp_template_cache = exp_templates


def _ship_nationality_type(template_id: int) -> tuple:
    key = int(template_id)
    cached = _statistics_nattype_cache.get(key)
    if cached is not None:
        return cached
    from src.orm.config_entry import get_config_entry_sync
    try:
        entry = get_config_entry_sync("sharecfgdata/ship_data_statistics.json", str(key))
    except Exception:
        entry = None
    data = _entry_data(entry)
    nat_type = None
    if data is not None:
        try:
            nat_type = (int(data.get("nationality", 0) or 0), int(data.get("type", 0) or 0))
        except (TypeError, ValueError):
            nat_type = None
    if nat_type is None:
        nat_type = (-1, -1)
    _statistics_nattype_cache[key] = nat_type
    return nat_type


_open_need_cache = {}    # task_id -> tuple of open_need task ids


def _task_open_need(task_id: int) -> tuple:
    """The task template's open_need list (task ids that must be CLAIMED --
    submit_time > 0 -- before this dev-chain mission may open; the client
    refuses ON_TASK_OPEN via TaskProxy.isFinishPrevTasks for the same list,
    e.g. Combat Data Collection Ⅱ needs 60012)."""
    key = int(task_id)
    cached = _open_need_cache.get(key)
    if cached is not None:
        return cached
    from src.orm.config_entry import get_config_entry_sync
    try:
        entry = get_config_entry_sync("sharecfgdata/task_data_template.json", str(key))
    except Exception:
        entry = None
    data = _entry_data(entry)
    raw = data.get("open_need", []) if isinstance(data, dict) else []
    need = []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            try:
                nid = int(item or 0)
            except (TypeError, ValueError):
                continue
            if nid:
                need.append(nid)
    result = tuple(need)
    _open_need_cache[key] = result
    return result


def is_dev_chain_task_open(commander_id: int, task_id: int, now: int = None) -> Optional[bool]:
    """Gate ANY Dev Dock chain mission (sub_type 1041 Combat Data Collection,
    110 Theoretical Research, 1000 Design Breakthrough, ...). A mission only
    accrues while its blueprint's development is running, its 24h unlock
    offset has passed (the client's WAIT state) AND every task in its
    open_need list has been submitted -- the client renders the mission as
    OPENING (refusing accrual) until then. Returns True when collectable,
    False when locked/not-started, None for non-dev-chain tasks (no gating,
    keep the accept-on-progress behaviour)."""
    import time as _t
    _ensure_dev_chain_caches()
    if now is None:
        now = int(_t.time())
    meta = _chain_meta_cache.get(int(task_id))
    if meta is None:
        return None
    blueprint_id, offset = meta
    from src.db.store import get_default_store
    store = get_default_store()
    if store is None:
        return False
    try:
        row = store.fetchrow(
            "SELECT start_time FROM commander_shipyard_blueprints "
            "WHERE commander_id = $1 AND blueprint_id = $2 AND ship_id = 0 AND start_time > 0",
            commander_id, blueprint_id,
        )
    except Exception:
        row = None
    if row is None:
        return False
    if now < int(row[0] or 0) + int(offset) + 1:
        return False
    for need_id in _task_open_need(task_id):
        try:
            claimed = store.fetchval(
                "SELECT 1 FROM commander_tasks "
                "WHERE commander_id = $1 AND task_id = $2 AND submit_time > 0",
                commander_id, need_id,
            )
        except Exception:
            return False
        if not claimed:
            return False
    return True


def advance_shipyard_combat_data_tasks(client, ship_exp_gains: dict, system: int) -> list:
    """Accumulate battle EXP into the commander's in-progress dev-chain
    BATTLE_EXP missions (sub_type 1041). Returns the task ids whose progress
    changed (caller pushes SC_20002). Only battles in supported systems and
    only missions whose 24h unlock offset has passed are touched, so a locked
    mission never accrues before the client opens it."""
    if not ship_exp_gains or system not in _COMBAT_DATA_COUNT_SYSTEMS:
        return []
    commander = getattr(client, "commander", None)
    if commander is None:
        return []
    commander_id = getattr(commander, "commander_id", 0)
    if not commander_id:
        return []
    _ensure_dev_chain_caches()
    from src.db.store import get_default_store
    store = get_default_store()
    if store is None or not _chain_meta_cache or not _exp_template_cache:
        return []

    now = int(__import__("time").time())
    try:
        dev_rows = store.fetch(
            "SELECT blueprint_id, start_time FROM commander_shipyard_blueprints "
            "WHERE commander_id = $1 AND ship_id = 0 AND start_time > 0",
            commander_id,
        )
    except Exception:
        dev_rows = []
    if not dev_rows:
        return []
    start_by_bp = {int(r[0]): int(r[1] or 0) for r in dev_rows}

    # Resolve each gaining ship to its (nationality, type) once per template.
    owned_map = getattr(commander, "owned_ships_map", None) or {}
    exp_by_category = {}
    if hasattr(owned_map, "get"):
        for ship_id, gain in ship_exp_gains.items():
            gain = int(gain or 0)
            if gain <= 0:
                continue
            owned = owned_map.get(ship_id)
            if owned is None:
                continue
            template_id = owned.get("ship_id", 0) if isinstance(owned, dict) else getattr(owned, "ship_id", 0)
            if not template_id:
                continue
            cat = _ship_nationality_type(template_id)
            exp_by_category[cat] = exp_by_category.get(cat, 0) + gain
    if not exp_by_category:
        return []

    # Candidate missions: tasks of a started blueprint whose open offset passed
    # AND whose open_need chain (e.g. Combat Data Collection Ⅰ submitted) is
    # satisfied -- officially a later stage never counts before the earlier one
    # is claimed, even when its time offset has already elapsed.
    candidates = []  # (task_id, pairs, target_num)
    for bp_id, start in start_by_bp.items():
        for tid, (owner_bp, offset) in _chain_meta_cache.items():
            if owner_bp != bp_id:
                continue
            template = _exp_template_cache.get(tid)
            if template is None:
                continue
            if now < start + int(offset) + 1:
                continue
            if not is_dev_chain_task_open(commander_id, tid, now):
                continue
            candidates.append((tid, template[0], template[1]))
    if not candidates:
        return []

    delta_by_task = {}
    for tid, pairs, target_num in candidates:
        total = 0
        for cat, gained in exp_by_category.items():
            if cat in pairs:
                total += gained
        if total > 0:
            delta_by_task[tid] = (total, target_num)
    if not delta_by_task:
        return []

    from src.orm.commander_task import upsert_task_progress_least
    updated = []
    for tid, (delta, target_num) in delta_by_task.items():
        try:
            upsert_task_progress_least(commander_id, tid, delta, target_num, now)
            updated.append(tid)
        except Exception:
            pass
    return updated


async def emit_shipyard_combat_data(client, ship_exp_gains: dict, system: int):
    try:
        updated = advance_shipyard_combat_data_tasks(client, ship_exp_gains, system)
        if updated:
            from src.answer.task_handlers import _push_progress_update
            _push_progress_update(client, updated)
            await client.flush()
    except Exception:
        pass


def schedule_shipyard_combat_data(client, ship_exp_gains: dict, system: int):
    """Fire the dev-chain combat-data accrual without blocking the caller.
    Mirrors task_handlers.schedule_emit: create_task in a live loop, otherwise
    run to completion so synchronous tests still apply progress."""
    import asyncio
    coro = emit_shipyard_combat_data(client, ship_exp_gains, system)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        loop.create_task(coro)
    else:
        try:
            asyncio.run(coro)
        except RuntimeError:
            pass
