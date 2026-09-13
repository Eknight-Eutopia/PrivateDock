from typing import Any

from src.protobuf import protobuf
from src.orm.config_entry import fetch_config_entry_data, fetch_config_entries_data, upsert_config_entry_data

FLEET_TECH_STATE_CATEGORY = "runtime/fleet_tech_state"
FLEET_TECH_GROUP_CATEGORY = "ShareCfg/fleet_tech_group.json"
FLEET_TECH_TEMPLATE_CATEGORY = "ShareCfg/fleet_tech_template.json"

RESULT_FAILURE = 1
RESULT_SUCCESS = 0
ONE_STEP_CLAIM_TYPE = 1


list_config_entries = fetch_config_entries_data


def load_fleet_tech_configs():
    group_entries = list_config_entries(FLEET_TECH_GROUP_CATEGORY)
    template_entries = list_config_entries(FLEET_TECH_TEMPLATE_CATEGORY)

    groups = {}
    for entry in group_entries:
        gid = entry.get("id", 0)
        if gid == 0:
            continue
        groups[gid] = {
            "id": gid,
            "techs": entry.get("techs", []),
        }

    templates = {}
    for entry in template_entries:
        tid = entry.get("id", 0)
        if tid == 0:
            continue
        templates[tid] = {
            "id": tid,
            "groupid": entry.get("groupid", 0),
            "cost": entry.get("cost", 0),
            "time": entry.get("time", 0),
            "add": entry.get("add", []),
            "level_award_display": entry.get("level_award_display", []),
        }

    return groups, templates


def fleet_tech_index_of_tech(group: dict, tech_id: int) -> int:
    techs = group.get("techs", [])
    for i, tid in enumerate(techs):
        if tid == tech_id:
            return i
    return -1


def fleet_tech_expected_next_tech(group: dict, effect_tech_id: int):
    techs = group.get("techs", [])
    if not techs:
        return 0, False
    if effect_tech_id == 0:
        return techs[0], True
    current_index = fleet_tech_index_of_tech(group, effect_tech_id)
    if current_index < 0:
        return 0, False
    next_index = current_index + 1
    if next_index >= len(techs):
        return 0, False
    return techs[next_index], True


def fleet_tech_has_active_study(state: dict) -> bool:
    for g in state.get("groups", []):
        if g.get("study_tech_id", 0) != 0:
            return True
    return False


def parse_uint32_value(value: Any):
    if isinstance(value, (int, float)):
        v = int(value)
        if v < 0:
            return 0, False
        return v, True
    if isinstance(value, str):
        try:
            v = int(value)
            if v < 0:
                return 0, False
            return v, True
        except (ValueError, TypeError):
            return 0, False
    return 0, False


def fleet_tech_apply_template_additions(max_dict: dict, raw_add: list):
    for raw_entry in raw_add:
        if not isinstance(raw_entry, list) or len(raw_entry) < 3:
            continue
        ship_types = raw_entry[0]
        if not isinstance(ship_types, list):
            continue
        attr_type, ok = parse_uint32_value(raw_entry[1])
        if not ok or attr_type == 0:
            continue
        value, ok = parse_uint32_value(raw_entry[2])
        if not ok:
            continue
        for raw_ship_type in ship_types:
            ship_type, ok = parse_uint32_value(raw_ship_type)
            if not ok or ship_type == 0:
                continue
            key = (ship_type, attr_type)
            max_dict[key] = max_dict.get(key, 0) + value


def fleet_tech_build_max_additions(state: dict, groups: dict, templates: dict) -> dict:
    max_dict = {}
    for group_state in state.get("groups", []):
        group_id = group_state.get("group_id", 0)
        group = groups.get(group_id)
        if group is None:
            continue
        completed_index = fleet_tech_index_of_tech(group, group_state.get("effect_tech_id", 0))
        if completed_index < 0:
            continue
        techs = group.get("techs", [])
        for i in range(completed_index + 1):
            template = templates.get(techs[i])
            if template is None:
                continue
            fleet_tech_apply_template_additions(max_dict, template.get("add", []))
    return max_dict


def fleet_tech_build_tech_set_list(state: dict, max_dict: dict):
    result = []
    for override in state.get("attr_overrides", []):
        key = (override.get("ship_type", 0), override.get("attr_type", 0))
        max_value = max_dict.get(key, 0)
        if max_value == 0:
            continue
        set_value = override.get("set_value", 0)
        if set_value > max_value:
            continue
        if set_value == max_value:
            continue
        ts = protobuf.TECHSET()
        ts.ship_type = override.get("ship_type", 0)
        ts.attr_type = override.get("attr_type", 0)
        ts.set_value = set_value
        result.append(ts)
    result.sort(key=lambda x: (x.ship_type, x.attr_type))
    return result


def fleet_tech_normalize_overrides(payload: list, max_dict: dict):
    if not payload:
        return [], True
    index = {}
    overrides = []
    for ts in payload:
        if ts is None:
            return None, False
        ship_type = ts.ship_type
        attr_type = ts.attr_type
        set_value = ts.set_value
        if ship_type == 0 or attr_type == 0:
            return None, False
        key = (ship_type, attr_type)
        max_value = max_dict.get(key, 0)
        if max_value == 0:
            return None, False
        if set_value > max_value:
            return None, False
        normalized = {"ship_type": ship_type, "attr_type": attr_type, "set_value": set_value}
        if key in index:
            overrides[index[key]] = normalized
            continue
        index[key] = len(overrides)
        overrides.append(normalized)
    effective = []
    for override in overrides:
        key = (override["ship_type"], override["attr_type"])
        max_value = max_dict.get(key, 0)
        if override["set_value"] == max_value:
            continue
        effective.append(override)
    effective.sort(key=lambda x: (x["ship_type"], x["attr_type"]))
    return effective, True


def fleet_tech_claim_drops(template: dict):
    merged = {}
    for raw_reward in template.get("level_award_display", []):
        if not isinstance(raw_reward, list) or len(raw_reward) < 3:
            continue
        drop_type, ok = parse_uint32_value(raw_reward[0])
        if not ok:
            continue
        drop_id, ok = parse_uint32_value(raw_reward[1])
        if not ok:
            continue
        count, ok = parse_uint32_value(raw_reward[2])
        if not ok or count == 0:
            continue
        key = f"{drop_type}:{drop_id}"
        if key in merged:
            merged[key].number += count
            continue
        drop = protobuf.DROPINFO()
        drop.type = drop_type
        drop.id = drop_id
        drop.number = count
        merged[key] = drop
    return fleet_tech_drop_map_to_slice(merged)


def fleet_tech_merge_drop_list(merged: dict, drops: list):
    for drop in drops:
        if drop is None:
            continue
        key = f"{drop.type}:{drop.id}"
        if key in merged:
            merged[key].number += drop.number
            continue
        d = protobuf.DROPINFO()
        d.type = drop.type
        d.id = drop.id
        d.number = drop.number
        merged[key] = d


def fleet_tech_drop_map_to_slice(merged: dict):
    result = list(merged.values())
    result.sort(key=lambda x: (x.type, x.id))
    return result


def get_or_create_commander_fleet_tech_state(commander_id: int) -> dict:
    state = fetch_config_entry_data(FLEET_TECH_STATE_CATEGORY, commander_id)
    if state is not None:
        _ensure_fleet_tech_defaults(state, commander_id)
        return state
    state = {"commander_id": commander_id, "groups": [], "attr_overrides": []}
    save_commander_fleet_tech_state(commander_id, state)
    return state


def save_commander_fleet_tech_state(commander_id: int, state: dict):
    _ensure_fleet_tech_defaults(state, commander_id)
    upsert_config_entry_data(FLEET_TECH_STATE_CATEGORY, commander_id, state)


def _ensure_fleet_tech_defaults(state: dict, commander_id: int):
    if state.get("commander_id", 0) == 0:
        state["commander_id"] = commander_id
    if "groups" not in state or state["groups"] is None:
        state["groups"] = []
    if "attr_overrides" not in state or state["attr_overrides"] is None:
        state["attr_overrides"] = []
    state["groups"].sort(key=lambda x: x.get("group_id", 0))
    state["attr_overrides"].sort(key=lambda x: (x.get("ship_type", 0), x.get("attr_type", 0)))


def fleet_tech_upsert_group(state: dict, group_id: int) -> dict:
    for g in state["groups"]:
        if g.get("group_id", 0) == group_id:
            return g
    new_group = {"group_id": group_id, "effect_tech_id": 0, "study_tech_id": 0, "study_finish_time": 0, "rewarded_tech_id": 0}
    state["groups"].append(new_group)
    _ensure_fleet_tech_defaults(state, state.get("commander_id", 0))
    for g in state["groups"]:
        if g.get("group_id", 0) == group_id:
            return g
    return new_group


def fleet_tech_get_group(state: dict, group_id: int):
    for g in state.get("groups", []):
        if g.get("group_id", 0) == group_id:
            return g, True
    return None, False


def fleet_tech_set_attr_overrides(state: dict, overrides: list):
    if overrides is None:
        overrides = []
    state["attr_overrides"] = overrides
    _ensure_fleet_tech_defaults(state, state.get("commander_id", 0))
