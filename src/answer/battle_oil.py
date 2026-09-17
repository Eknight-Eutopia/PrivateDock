"""Per-battle fleet oil charging — mirrors the original client formulas.

Client reference (EN Lua):
- ``mod/battle/command/gate/battlegatescenario.lua`` — Entrance charges the
  fleet's START cost after SC_40002 arrives; Exit charges the END cost plus
  the called-in submarines' end cost after the battle result.
- ``model/vo/fleet.lua`` GetCostSum/getStartCost/getEndCost — per-ship sums
  (a submarine fleet pays end cost only; submarines never pay start cost).
- ``model/vo/ship.lua`` getStartBattleExpend/getEndBattleExpend —
  start = ``ship_data_template[configId].oil_at_start`` (0 for submarine
  types), end = ``floor(oil_at_end * ship_level[level].fight_oil_ratio / 10000)``.
- ``model/vo/chapter.lua`` GetLimitOilCost + ``chapterleveldata.lua``
  getFleetCost — on loop chapters (loop_flag != 0) carrying ``use_oil_limit``,
  the END cost is clamped so start + end <= limit (index 1 normal / 2 boss /
  3 submarine fleet); submarine support is clamped to limit directly.
- ``model/vo/chapter.lua`` GetExtraCostRate — every active ``more_oil``
  operation buff adds ``benefit_effect * 0.01`` (the High-Efficiency Combat
  Logistics Plan buff = +1.0, i.e. doubled oil), floor 1.0.
- ``sharecfg/battle_cost_template.lua`` — systems with ``oil_cost == 0``
  (exercise/duel, Operation Siren, ...) are never charged.

The flat chapter-start cost (``chapter_template.oil``) is charged separately
in ``handle_chapter_tracking`` (src/answer/chapter/handlers.py) — the client
consumes the same amount on CS_13102 success.
"""

import math

# battle_cost_template entries with oil_cost = 1 (client sharecfg).
OIL_COST_SYSTEMS = frozenset({1, 2, 8, 9, 11, 12, 16, 17, 18})

# chapterconst.lua ExpeditionTypeBoss / ExpeditionTypeMulBoss — boss stages
# use use_oil_limit[2] instead of [1] on capped loop chapters.
_EXPEDITION_TYPE_BOSS = 99
_EXPEDITION_TYPE_MUL_BOSS = 94

# ship types counted as submarines (battle_session.SUBMARINE_SHIP_TYPE_IDS —
# duplicated here to avoid a circular import; battle_session imports this
# module).
_SUBMARINE_SHIP_TYPE_IDS = (8, 14, 17)

_SHIP_DATA_TEMPLATE_CATEGORY = "sharecfgdata/ship_data_template.json"
_SHIP_DATA_STATISTICS_CATEGORY = "sharecfgdata/ship_data_statistics.json"
_SHIP_LEVEL_CATEGORY = "ShareCfg/ship_level.json"
_EXPEDITION_TEMPLATE_CATEGORY = "sharecfgdata/expedition_data_template.json"
_CHAPTER_TEMPLATE_CATEGORY = "sharecfgdata/chapter_template.json"

_oil_config_cache: dict = {}


def _config_value(category: str, key):
    if category not in _oil_config_cache:
        _oil_config_cache[category] = {}
    cache = _oil_config_cache[category]
    if key not in cache:
        from src.orm.config_entry import fetch_config_entry_data
        cache[key] = fetch_config_entry_data(category, str(key))
    return cache[key]


def _owned_ship_config(owned) -> dict:
    """The ship's config dict (type/rarity/...). The live owned_ships_map
    entries carry no nested "ship" — fall back to ship_data_statistics by
    the entry's template id."""
    if owned is None:
        return {}
    ship = owned.get("ship") if isinstance(owned, dict) else getattr(owned, "ship", None)
    if not isinstance(ship, dict):
        ship = _config_value(_SHIP_DATA_STATISTICS_CATEGORY, _owned_ship_id(owned))
    return ship if isinstance(ship, dict) else {}


def _owned_ship_level(owned) -> int:
    if owned is None:
        return 1
    level = owned.get("level") if isinstance(owned, dict) else getattr(owned, "level", 1)
    try:
        return int(level or 1)
    except (TypeError, ValueError):
        return 1


def _is_submarine(owned) -> bool:
    stype = _owned_ship_config(owned).get("type", 0)
    try:
        return int(stype) in _SUBMARINE_SHIP_TYPE_IDS
    except (TypeError, ValueError):
        return False


def ship_oil_start(owned) -> int:
    """oil_at_start of one ship (0 for submarines)."""
    if owned is None or _is_submarine(owned):
        return 0
    template = _config_value(_SHIP_DATA_TEMPLATE_CATEGORY, _owned_ship_id(owned))
    if not isinstance(template, dict):
        return 0
    try:
        return int(template.get("oil_at_start", 0) or 0)
    except (TypeError, ValueError):
        return 0


def ship_oil_end(owned) -> int:
    """floor(oil_at_end * fight_oil_ratio(level) / 10000) of one ship."""
    if owned is None:
        return 0
    template = _config_value(_SHIP_DATA_TEMPLATE_CATEGORY, _owned_ship_id(owned))
    if not isinstance(template, dict):
        return 0
    try:
        oil_at_end = int(template.get("oil_at_end", 0) or 0)
    except (TypeError, ValueError):
        return 0
    ratio = _fight_oil_ratio(_owned_ship_level(owned))
    return int(math.floor(oil_at_end * ratio / 10000))


def _owned_ship_id(owned):
    if owned is None:
        return "0"
    ship_id = owned.get("ship_id") if isinstance(owned, dict) else getattr(owned, "ship_id", 0)
    return str(ship_id or 0)


def _fight_oil_ratio(level: int) -> int:
    """fight_oil_ratio (basis points) from ShareCfg/ship_level; beyond the
    table the client uses the last entry (getConfigFromLevel1 fallback)."""
    entry = _config_value(_SHIP_LEVEL_CATEGORY, level)
    if entry is None:
        # Level above the table (or missing data): fall back to the table's
        # highest level, mirroring getConfigFromLevel1's `or slot0[#all]`.
        from src.orm.config_entry import fetch_config_entries_data
        rows = fetch_config_entries_data(_SHIP_LEVEL_CATEGORY)
        if not rows:
            return 10000
        best = None
        for row in rows:
            try:
                lv = int(row.get("level", 0) or 0)
            except (TypeError, ValueError):
                continue
            if best is None or lv > best[0]:
                best = (lv, row)
        entry = best[1] if best else None
    if not isinstance(entry, dict):
        return 10000
    try:
        return int(entry.get("fight_oil_ratio", 10000) or 10000)
    except (TypeError, ValueError):
        return 10000


def _chapter_context(commander_id: int, stage_id: int):
    """(extra_cost_rate, oil_limit) for a chapter battle, or (1.0, None) when
    the stage is not a battle of the commander's tracked chapter."""
    from src.orm.chapter import get_chapter_state_sync
    state = get_chapter_state_sync(commander_id)
    if state is None or not state.state:
        return 1.0, None
    from src.protobuf import protobuf
    current = protobuf.CURRENTCHAPTERINFO()
    try:
        current.ParseFromString(bytes(state.state))
    except Exception:
        return 1.0, None

    from src.answer.battle_session import _is_chapter_battle
    if not _is_chapter_battle(current, stage_id):
        return 1.0, None

    rate = _extra_cost_rate(list(current.operation_buff))

    limit = None
    if current.loop_flag:
        from src.answer.chapter.helpers import load_chapter_template
        template = load_chapter_template(current.id, current.loop_flag)
        oil_limit = getattr(template, "use_oil_limit", None) if template else None
        if oil_limit:
            limit = oil_limit
    return rate, limit


def _extra_cost_rate(operation_buff_ids) -> float:
    """client chapter.lua GetExtraCostRate: 1 + sum(more_oil benefit_effect)*0.01."""
    from src.answer.chapter.helpers import _load_benefit_buff
    rate = 1.0
    for buff_id in operation_buff_ids:
        entry = _load_benefit_buff(int(buff_id))
        if entry is None or entry.get("benefit_type") != "more_oil":
            continue
        try:
            rate += float(entry.get("benefit_effect", 0)) * 0.01
        except (TypeError, ValueError):
            continue
    return max(1.0, rate)


def _oil_limit_index(stage_id: int, system: int, oil_limit: dict) -> int:
    if system == 11:  # BATTLE_SYSTEM_SUB — submarine fleet, index 3
        return oil_limit.get(3) or 9999
    expedition = _config_value(_EXPEDITION_TEMPLATE_CATEGORY, stage_id)
    exp_type = expedition.get("type") if isinstance(expedition, dict) else None
    if exp_type in (_EXPEDITION_TYPE_BOSS, _EXPEDITION_TYPE_MUL_BOSS):
        return oil_limit.get(2) or 9999
    return oil_limit.get(1) or 9999


def _fleet_owners(client, ship_ids) -> list:
    owned_map = getattr(client.commander, "owned_ships_map", None) or {}
    return [owned_map.get(sid) for sid in ship_ids if owned_map.get(sid) is not None]


def charge_battle_oil_start(client, system: int, stage_id: int, ship_ids) -> None:
    """Charge the entering fleet's START cost at battle entrance (client
    battlegatescenario.Entrance)."""
    if system not in OIL_COST_SYSTEMS:
        return
    ships = _fleet_owners(client, ship_ids)
    start = sum(ship_oil_start(s) for s in ships)
    if start <= 0:
        return
    rate, _ = _chapter_context(client.commander.commander_id, stage_id)
    cost = int(start * rate)
    if cost > 0:
        client.commander.consume_resource(2, cost)


def charge_battle_oil_end(client, system: int, stage_id: int, ship_ids, extra_participant_ids) -> None:
    """Charge the fleet's END cost (+ called-in submarines' end cost) at
    battle exit (client battlegatescenario.Exit). Sunk ships still pay the
    end cost (the client's exit uses getShips(true))."""
    if system not in OIL_COST_SYSTEMS:
        return
    ships = _fleet_owners(client, ship_ids)
    if not ships:
        return
    raw_start = sum(ship_oil_start(s) for s in ships)
    fleet_end = sum(ship_oil_end(s) for s in ships)
    sub_end = 0
    for owned in _fleet_owners(client, extra_participant_ids):
        if _is_submarine(owned):
            sub_end += ship_oil_end(owned)
        else:
            fleet_end += ship_oil_end(owned)

    rate, oil_limit = _chapter_context(client.commander.commander_id, stage_id)
    if oil_limit is not None:
        limit = _oil_limit_index(stage_id, system, oil_limit)
        fleet_end = min(fleet_end, max(0, limit - raw_start))
        sub_end = min(sub_end, limit)

    cost = int((fleet_end + sub_end) * rate)
    if cost > 0:
        client.commander.consume_resource(2, cost)


def invalidate_oil_config_cache() -> None:
    """Called after a data re-import so stale oil configs are not served."""
    _oil_config_cache.clear()
