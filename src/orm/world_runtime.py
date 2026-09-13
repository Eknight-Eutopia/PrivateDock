from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.config_entry import ConfigEntry, get_config_entry_sync
from datetime import timedelta
from src.region.region import offset as _region_offset

_WORLD_RUNTIME_CATEGORY = "Runtime/world_runtime.json"
_WORLD_GAMESET_CATEGORY = "ShareCfg/gameset.json"
_WORLD_GAMESET_CATEGORY_LOWER = "sharecfgdata/gameset.json"
_WORLD_MOVE_POWER_MAX_KEY = "world_movepower_maxvalue"
_WORLD_MOVE_POWER_RECOVERY_KEY = "world_movepower_recovery_interval"
_DEFAULT_WORLD_MOVE_POWER_MAX = 200
_DEFAULT_WORLD_MOVE_POWER_RECOVERY = 600


@dataclass
class WorldRuntime:
    commander_id: int = 0
    camp: int = 0
    map_id: int = 0
    enter_map_id: int = 0
    action_power: int = 0
    action_power_extra: int = 0
    action_power_fetch_count: int = 0
    last_recover_timestamp: int = 0
    last_change_group_timestamp: int = 0
    progress: int = 0
    task_finish_count: int = 0
    stamina_exchange_times: int = 0
    round: int = 0
    week_start_unix: int = 0
    month_key: int = 0
    sairen_chapter: list[int] = field(default_factory=list)
    map_template_by_random_id: dict[str, int] = field(default_factory=dict)
    fleet_ship_ids: list[int] = field(default_factory=list)
    commander_ids: list[int] = field(default_factory=list)
    reset_available_at_timestamp: int = 0


from src.shopreset.framework import current_weekly_reset_unix as _current_weekly_reset_unix


def _current_month_key(now: datetime) -> int:
    offset = _region_offset()
    local_ts = now.timestamp() + offset
    local_dt = datetime.fromtimestamp(local_ts, tz=timezone.utc)
    return local_dt.year * 100 + local_dt.month


from src.orm.config_entry import upsert_config_entry as _upsert_config_entry


def load_world_runtime(commander_id: int) -> Optional[WorldRuntime]:
    entry = get_config_entry_sync(_WORLD_RUNTIME_CATEGORY, str(commander_id))
    if entry is None:
        return None
    data = entry.data
    if data is None:
        return None
    runtime = WorldRuntime(
        commander_id=commander_id,
        camp=data.get("camp", 0),
        map_id=data.get("map_id", 0),
        enter_map_id=data.get("enter_map_id", 0),
        action_power=data.get("action_power", 0),
        action_power_extra=data.get("action_power_extra", 0),
        action_power_fetch_count=data.get("action_power_fetch_count", 0),
        last_recover_timestamp=data.get("last_recover_timestamp", 0),
        last_change_group_timestamp=data.get("last_change_group_timestamp", 0),
        progress=data.get("progress", 0),
        task_finish_count=data.get("task_finish_count", 0),
        stamina_exchange_times=data.get("stamina_exchange_times", 0),
        round=data.get("round", 0),
        week_start_unix=data.get("week_start_unix", 0),
        month_key=data.get("month_key", 0),
        sairen_chapter=[int(s) for s in data.get("sairen_chapter", [])],
        map_template_by_random_id={str(k): int(v) for k, v in data.get("map_template_by_random_id", {}).items()},
        fleet_ship_ids=[int(f) for f in data.get("fleet_ship_ids", [])],
        commander_ids=[int(c) for c in data.get("commander_ids", [])],
        reset_available_at_timestamp=data.get("reset_available_at_timestamp", 0),
    )
    runtime.commander_id = commander_id
    if runtime.map_template_by_random_id is None:
        runtime.map_template_by_random_id = {}
    return runtime


def load_or_create_world_runtime(commander_id: int) -> WorldRuntime:
    runtime = load_world_runtime(commander_id)
    if runtime is not None:
        return runtime
    return WorldRuntime(
        commander_id=commander_id,
        action_power=200,
        action_power_extra=0,
        action_power_fetch_count=0,
        last_recover_timestamp=0,
        last_change_group_timestamp=0,
        progress=0,
        task_finish_count=0,
        stamina_exchange_times=0,
        round=0,
        sairen_chapter=[],
        map_template_by_random_id={},
        fleet_ship_ids=[],
        commander_ids=[],
    )


def save_world_runtime(runtime: WorldRuntime) -> None:
    if runtime is None:
        raise ValueError("world runtime is None")
    if runtime.map_template_by_random_id is None:
        runtime.map_template_by_random_id = {}
    if runtime.sairen_chapter is None:
        runtime.sairen_chapter = []
    payload = {
        "commander_id": runtime.commander_id,
        "camp": runtime.camp,
        "map_id": runtime.map_id,
        "enter_map_id": runtime.enter_map_id,
        "action_power": runtime.action_power,
        "action_power_extra": runtime.action_power_extra,
        "action_power_fetch_count": runtime.action_power_fetch_count,
        "last_recover_timestamp": runtime.last_recover_timestamp,
        "last_change_group_timestamp": runtime.last_change_group_timestamp,
        "progress": runtime.progress,
        "task_finish_count": runtime.task_finish_count,
        "stamina_exchange_times": runtime.stamina_exchange_times,
        "round": runtime.round,
        "week_start_unix": runtime.week_start_unix,
        "month_key": runtime.month_key,
        "sairen_chapter": list(runtime.sairen_chapter),
        "map_template_by_random_id": dict(runtime.map_template_by_random_id),
        "fleet_ship_ids": list(runtime.fleet_ship_ids),
        "commander_ids": list(runtime.commander_ids),
        "reset_available_at_timestamp": runtime.reset_available_at_timestamp,
    }
    _upsert_config_entry(_WORLD_RUNTIME_CATEGORY, str(runtime.commander_id), payload)


def set_map_template(runtime: WorldRuntime, random_id: int, template_id: int) -> None:
    if runtime.map_template_by_random_id is None:
        runtime.map_template_by_random_id = {}
    runtime.map_template_by_random_id[str(random_id)] = template_id


def map_template(runtime: WorldRuntime, random_id: int) -> int:
    if runtime.map_template_by_random_id is None:
        return 0
    return runtime.map_template_by_random_id.get(str(random_id), 0)


def _load_world_gameset_key_value(key: str) -> int:
    entry = get_config_entry_sync(_WORLD_GAMESET_CATEGORY, key)
    if entry is None:
        entry = get_config_entry_sync(_WORLD_GAMESET_CATEGORY_LOWER, key)
    if entry is None or entry.data is None:
        return 0
    return int(entry.data.get("key_value", 0))


def load_world_move_power_settings() -> tuple[int, int]:
    max_value = _load_world_gameset_key_value(_WORLD_MOVE_POWER_MAX_KEY)
    recover_interval = _load_world_gameset_key_value(_WORLD_MOVE_POWER_RECOVERY_KEY)
    if max_value == 0:
        max_value = _DEFAULT_WORLD_MOVE_POWER_MAX
    if recover_interval == 0:
        recover_interval = _DEFAULT_WORLD_MOVE_POWER_RECOVERY
    return max_value, recover_interval


def _apply_world_action_power_regeneration(
    runtime: WorldRuntime, now_unix: int, max_action_power: int, recover_interval: int
) -> bool:
    if max_action_power == 0 or recover_interval == 0:
        return False
    if runtime.last_recover_timestamp == 0 or runtime.last_recover_timestamp > now_unix:
        runtime.last_recover_timestamp = now_unix
        return True
    if runtime.action_power >= max_action_power:
        if runtime.last_recover_timestamp == now_unix:
            return False
        runtime.last_recover_timestamp = now_unix
        return True
    elapsed = now_unix - runtime.last_recover_timestamp
    ticks = elapsed // recover_interval
    if ticks == 0:
        return False
    missing = max_action_power - runtime.action_power
    gain = ticks
    if gain > missing:
        gain = missing
    runtime.action_power += gain
    runtime.last_recover_timestamp += gain * recover_interval
    if runtime.action_power >= max_action_power:
        runtime.last_recover_timestamp = now_unix
    return True


def sync_world_runtime(runtime: WorldRuntime, now: Optional[datetime] = None) -> tuple[bool, bool]:
    if runtime is None:
        raise ValueError("world runtime is None")
    if now is None:
        now = datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    week_start_unix = _current_weekly_reset_unix(now)
    month_key = _current_month_key(now)
    changed = False
    month_reset = False
    if runtime.week_start_unix == 0:
        runtime.week_start_unix = week_start_unix
        changed = True
    elif runtime.week_start_unix != week_start_unix:
        runtime.week_start_unix = week_start_unix
        runtime.stamina_exchange_times = 0
        changed = True
    if runtime.month_key == 0:
        runtime.month_key = month_key
        changed = True
    elif runtime.month_key != month_key:
        runtime.month_key = month_key
        runtime.stamina_exchange_times = 0
        changed = True
        month_reset = True
    max_action_power, recover_interval = load_world_move_power_settings()
    if _apply_world_action_power_regeneration(runtime, int(now.timestamp()), max_action_power, recover_interval):
        changed = True
    return changed, month_reset
