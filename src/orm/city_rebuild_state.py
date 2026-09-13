from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.config_entry import ConfigEntry, get_config_entry_sync

_CITY_REBUILD_STATE_CATEGORY = "Runtime/city_rebuild_state"


@dataclass
class CityRebuildRecruit:
    id: int = 0
    start_time: int = 0


@dataclass
class CityRebuildState:
    commander_id: int = 0
    act_id: int = 0
    pt: int = 0
    builds: list[int] = field(default_factory=list)
    roles: list[int] = field(default_factory=list)
    recruits: list[CityRebuildRecruit] = field(default_factory=list)
    buffs: dict[int, int] = field(default_factory=dict)
    max_level: int = 0
    cur_level: int = 0
    max_display: int = 0
    adjust_time: int = 0
    adjust_left_hp: int = 0
    adjust_max_level: int = 0
    summary_pt: int = 0
    summary_ready: bool = False


from src.orm.config_entry import upsert_config_entry as _upsert_config_entry


def _city_rebuild_state_key(commander_id: int, act_id: int) -> str:
    return f"{commander_id}:{act_id}"


def _unique_sorted_uint32(values: list[int]) -> list[int]:
    if not values:
        return []
    return sorted(set(values))


def _unique_sorted_recruits(values: list[CityRebuildRecruit]) -> list[CityRebuildRecruit]:
    if not values:
        return []
    index: dict[int, CityRebuildRecruit] = {}
    for recruit in values:
        if recruit.id == 0:
            continue
        if recruit.id not in index or recruit.start_time < index[recruit.id].start_time:
            index[recruit.id] = recruit
    return sorted(index.values(), key=lambda r: r.id)


def _default_city_rebuild_state(commander_id: int, act_id: int) -> CityRebuildState:
    return CityRebuildState(
        commander_id=commander_id,
        act_id=act_id,
        builds=[],
        roles=[],
        recruits=[],
        buffs={},
        max_level=1,
        cur_level=1,
        max_display=1,
    )


def _normalize_city_rebuild_state(state: CityRebuildState, commander_id: int, act_id: int) -> None:
    state.commander_id = commander_id
    state.act_id = act_id
    if state.builds is None:
        state.builds = []
    if state.roles is None:
        state.roles = []
    if state.recruits is None:
        state.recruits = []
    if state.buffs is None:
        state.buffs = {}
    if state.max_level == 0:
        state.max_level = 1
    if state.cur_level == 0:
        state.cur_level = 1
    if state.cur_level > state.max_level:
        state.cur_level = state.max_level
    if state.max_display < state.max_level:
        state.max_display = state.max_level
    if state.adjust_max_level == 0:
        state.adjust_max_level = state.max_level
    state.builds = _unique_sorted_uint32(state.builds)
    state.roles = _unique_sorted_uint32(state.roles)
    state.recruits = _unique_sorted_recruits(state.recruits)


def get_or_create_city_rebuild_state(commander_id: int, act_id: int) -> CityRebuildState:
    key = _city_rebuild_state_key(commander_id, act_id)
    entry = get_config_entry_sync(_CITY_REBUILD_STATE_CATEGORY, key)
    if entry is None:
        state = _default_city_rebuild_state(commander_id, act_id)
        save_city_rebuild_state(state)
        return state
    data = entry.data
    state = CityRebuildState(
        commander_id=data.get("commander_id", commander_id),
        act_id=data.get("act_id", act_id),
        pt=data.get("pt", 0),
        builds=[int(b) for b in data.get("builds", [])],
        roles=[int(r) for r in data.get("roles", [])],
        recruits=[
            CityRebuildRecruit(id=int(r.get("id", 0)), start_time=int(r.get("start_time", 0)))
            for r in data.get("recruits", [])
        ],
        buffs={int(k): int(v) for k, v in data.get("buffs", {}).items()},
        max_level=data.get("max_level", 0),
        cur_level=data.get("cur_level", 0),
        max_display=data.get("max_display", 0),
        adjust_time=data.get("adjust_time", 0),
        adjust_left_hp=data.get("adjust_left_hp", 0),
        adjust_max_level=data.get("adjust_max_level", 0),
        summary_pt=data.get("summary_pt", 0),
        summary_ready=data.get("summary_ready", False),
    )
    _normalize_city_rebuild_state(state, commander_id, act_id)
    return state


def save_city_rebuild_state(state: CityRebuildState) -> None:
    _normalize_city_rebuild_state(state, state.commander_id, state.act_id)
    payload = {
        "commander_id": state.commander_id,
        "act_id": state.act_id,
        "pt": state.pt,
        "builds": list(state.builds),
        "roles": list(state.roles),
        "recruits": [{"id": r.id, "start_time": r.start_time} for r in state.recruits],
        "buffs": {str(k): v for k, v in state.buffs.items()},
        "max_level": state.max_level,
        "cur_level": state.cur_level,
        "max_display": state.max_display,
        "adjust_time": state.adjust_time,
        "adjust_left_hp": state.adjust_left_hp,
        "adjust_max_level": state.adjust_max_level,
        "summary_pt": state.summary_pt,
        "summary_ready": state.summary_ready,
    }
    _upsert_config_entry(_CITY_REBUILD_STATE_CATEGORY, _city_rebuild_state_key(state.commander_id, state.act_id), payload)
