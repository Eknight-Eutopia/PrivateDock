from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.config_entry import ConfigEntry, get_config_entry_sync

_FLEET_TECH_STATE_CATEGORY = "runtime/fleet_tech_state"


@dataclass
class FleetTechGroupState:
    group_id: int = 0
    effect_tech_id: int = 0
    study_tech_id: int = 0
    study_finish_time: int = 0
    rewarded_tech_id: int = 0


@dataclass
class FleetTechAttrOverride:
    ship_type: int = 0
    attr_type: int = 0
    set_value: int = 0


@dataclass
class CommanderFleetTechState:
    commander_id: int = 0
    groups: list[FleetTechGroupState] = field(default_factory=list)
    attr_overrides: list[FleetTechAttrOverride] = field(default_factory=list)


from src.orm.config_entry import upsert_config_entry as _upsert_config_entry


def _ensure_defaults(state: CommanderFleetTechState, commander_id: int) -> None:
    if state.commander_id == 0:
        state.commander_id = commander_id
    if state.groups is None:
        state.groups = []
    if state.attr_overrides is None:
        state.attr_overrides = []
    state.groups.sort(key=lambda g: g.group_id)
    state.attr_overrides.sort(key=lambda o: (o.ship_type, o.attr_type))


def upsert_group(state: CommanderFleetTechState, group_id: int) -> FleetTechGroupState:
    for g in state.groups:
        if g.group_id == group_id:
            return g
    new_group = FleetTechGroupState(group_id=group_id)
    state.groups.append(new_group)
    _ensure_defaults(state, state.commander_id)
    for g in state.groups:
        if g.group_id == group_id:
            return g
    return new_group


def get_group(state: CommanderFleetTechState, group_id: int) -> Optional[FleetTechGroupState]:
    for g in state.groups:
        if g.group_id == group_id:
            return g
    return None


def set_attr_overrides(state: CommanderFleetTechState, overrides: list[FleetTechAttrOverride]) -> None:
    if overrides is None:
        overrides = []
    state.attr_overrides = overrides
    _ensure_defaults(state, state.commander_id)


def _state_to_dict(state: CommanderFleetTechState) -> dict:
    return {
        "commander_id": state.commander_id,
        "groups": [
            {
                "group_id": g.group_id,
                "effect_tech_id": g.effect_tech_id,
                "study_tech_id": g.study_tech_id,
                "study_finish_time": g.study_finish_time,
                "rewarded_tech_id": g.rewarded_tech_id,
            }
            for g in state.groups
        ],
        "attr_overrides": [
            {
                "ship_type": o.ship_type,
                "attr_type": o.attr_type,
                "set_value": o.set_value,
            }
            for o in state.attr_overrides
        ],
    }


def _dict_to_state(data: dict, commander_id: int) -> CommanderFleetTechState:
    return CommanderFleetTechState(
        commander_id=data.get("commander_id", commander_id),
        groups=[
            FleetTechGroupState(
                group_id=int(g.get("group_id", 0)),
                effect_tech_id=int(g.get("effect_tech_id", 0)),
                study_tech_id=int(g.get("study_tech_id", 0)),
                study_finish_time=int(g.get("study_finish_time", 0)),
                rewarded_tech_id=int(g.get("rewarded_tech_id", 0)),
            )
            for g in data.get("groups", [])
        ],
        attr_overrides=[
            FleetTechAttrOverride(
                ship_type=int(o.get("ship_type", 0)),
                attr_type=int(o.get("attr_type", 0)),
                set_value=int(o.get("set_value", 0)),
            )
            for o in data.get("attr_overrides", [])
        ],
    )


def get_commander_fleet_tech_state(commander_id: int) -> Optional[CommanderFleetTechState]:
    entry = get_config_entry_sync(_FLEET_TECH_STATE_CATEGORY, str(commander_id))
    if entry is None:
        return None
    state = _dict_to_state(entry.data, commander_id) if entry.data else CommanderFleetTechState(commander_id=commander_id)
    _ensure_defaults(state, commander_id)
    return state


def get_or_create_commander_fleet_tech_state(commander_id: int) -> CommanderFleetTechState:
    state = get_commander_fleet_tech_state(commander_id)
    if state is not None:
        return state
    state = CommanderFleetTechState(commander_id=commander_id, groups=[], attr_overrides=[])
    save_commander_fleet_tech_state(state)
    return state


def save_commander_fleet_tech_state(state: CommanderFleetTechState) -> None:
    if state is None:
        return
    _ensure_defaults(state, state.commander_id)
    payload = _state_to_dict(state)
    _upsert_config_entry(_FLEET_TECH_STATE_CATEGORY, str(state.commander_id), payload)
