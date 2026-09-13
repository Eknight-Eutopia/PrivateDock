from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.config_entry import ConfigEntry, get_config_entry_sync

_LEGACY_EDUCATE_STATE_CATEGORY = "Runtime/legacy_educate_state"


@dataclass
class LegacyEducateState:
    commander_id: int = 0
    call_name: str = ""
    target_id: int = 0
    favor_lv: int = 0
    favor_exp: int = 0
    had_adjustment: bool = False
    attrs: dict[int, int] = field(default_factory=dict)
    task_progress: dict[int, int] = field(default_factory=dict)
    option_records: dict[int, int] = field(default_factory=dict)
    resources: dict[int, int] = field(default_factory=dict)
    endings: list[int] = field(default_factory=list)
    qualifieds: list[int] = field(default_factory=list)


from src.orm.config_entry import upsert_config_entry as _upsert_config_entry


def _default_legacy_educate_state(commander_id: int) -> LegacyEducateState:
    return LegacyEducateState(
        commander_id=commander_id,
        call_name="CHILD_USERNAME_SC_27001",
        favor_lv=1,
        favor_exp=0,
        attrs={201: 0, 202: 0, 203: 0},
        task_progress={},
        option_records={},
        resources={3: 10},
        endings=[],
        qualifieds=[],
    )


def _normalize_legacy_educate_state(state: LegacyEducateState, commander_id: int) -> None:
    state.commander_id = commander_id
    if not state.call_name:
        state.call_name = "CHILD_USERNAME_SC_27001"
    if state.favor_lv == 0:
        state.favor_lv = 1
    if state.attrs is None:
        state.attrs = {}
    state.attrs.setdefault(201, 0)
    state.attrs.setdefault(202, 0)
    state.attrs.setdefault(203, 0)
    if state.task_progress is None:
        state.task_progress = {}
    if state.option_records is None:
        state.option_records = {}
    if state.resources is None:
        state.resources = {}
    state.resources.setdefault(3, 10)
    if state.endings is None:
        state.endings = []
    if state.qualifieds is None:
        state.qualifieds = []


def get_or_create_legacy_educate_state(commander_id: int) -> LegacyEducateState:
    entry = get_config_entry_sync(_LEGACY_EDUCATE_STATE_CATEGORY, str(commander_id))
    if entry is None:
        state = _default_legacy_educate_state(commander_id)
        save_legacy_educate_state(state)
        return state
    data = entry.data
    state = LegacyEducateState(
        commander_id=data.get("commander_id", commander_id),
        call_name=data.get("call_name", ""),
        target_id=data.get("target_id", 0),
        favor_lv=data.get("favor_lv", 0),
        favor_exp=data.get("favor_exp", 0),
        had_adjustment=data.get("had_adjustment", False),
        attrs={int(k): int(v) for k, v in data.get("attrs", {}).items()},
        task_progress={int(k): int(v) for k, v in data.get("task_progress", {}).items()},
        option_records={int(k): int(v) for k, v in data.get("option_records", {}).items()},
        resources={int(k): int(v) for k, v in data.get("resources", {}).items()},
        endings=[int(e) for e in data.get("endings", [])],
        qualifieds=[int(q) for q in data.get("qualifieds", [])],
    )
    _normalize_legacy_educate_state(state, commander_id)
    return state


def save_legacy_educate_state(state: LegacyEducateState) -> None:
    _normalize_legacy_educate_state(state, state.commander_id)
    payload = {
        "commander_id": state.commander_id,
        "call_name": state.call_name,
        "target_id": state.target_id,
        "favor_lv": state.favor_lv,
        "favor_exp": state.favor_exp,
        "had_adjustment": state.had_adjustment,
        "attrs": {str(k): v for k, v in state.attrs.items()},
        "task_progress": {str(k): v for k, v in state.task_progress.items()},
        "option_records": {str(k): v for k, v in state.option_records.items()},
        "resources": {str(k): v for k, v in state.resources.items()},
        "endings": list(state.endings),
        "qualifieds": list(state.qualifieds),
    }
    _upsert_config_entry(_LEGACY_EDUCATE_STATE_CATEGORY, str(state.commander_id), payload)
