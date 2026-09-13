from datetime import datetime, timezone, timedelta
from typing import Optional

from src.orm.config_entry import fetch_config_entry_data, upsert_config_entry_data
from src.protobuf import protobuf
from src.region.region import offset as _region_offset

GUILD_DUTY_COMMANDER = 1
GUILD_DUTY_DEPUTY = 2
GUILD_DUTY_ORDINARY = 3
GUILD_DUTY_RECRUIT = 4

WORLD_RUNTIME_CATEGORY = "Runtime/world_runtime.json"
WORLD_BOSS_STATE_CATEGORY = "runtime/world_boss_state"
WORLD_GAMESET_CATEGORY = "ShareCfg/gameset.json"
WORLD_GAMESET_CATEGORY_ALT = "sharecfgdata/gameset.json"
WORLD_MOVE_POWER_MAX_KEY = "world_movepower_maxvalue"
WORLD_MOVE_POWER_RECOVERY_KEY = "world_movepower_recovery_interval"
DEFAULT_WORLD_MOVE_POWER_MAX = 200
DEFAULT_WORLD_MOVE_POWER_RECOVERY = 600


get_config_entry = fetch_config_entry_data
upsert_config_entry = upsert_config_entry_data


def load_world_runtime(commander_id: int) -> Optional[dict]:
    entry = get_config_entry(WORLD_RUNTIME_CATEGORY, str(commander_id))
    if entry is None:
        return None
    runtime = entry
    runtime["commander_id"] = commander_id
    if "map_template_by_random_id" not in runtime or runtime["map_template_by_random_id"] is None:
        runtime["map_template_by_random_id"] = {}
    return runtime


def load_or_create_world_runtime(commander_id: int) -> dict:
    runtime = load_world_runtime(commander_id)
    if runtime is not None:
        return runtime
    return {
        "commander_id": commander_id,
        "camp": 0,
        "map_id": 0,
        "enter_map_id": 0,
        "action_power": DEFAULT_WORLD_MOVE_POWER_MAX,
        "action_power_extra": 0,
        "action_power_fetch_count": 0,
        "last_recover_timestamp": 0,
        "last_change_group_timestamp": 0,
        "progress": 0,
        "task_finish_count": 0,
        "stamina_exchange_times": 0,
        "round": 0,
        "week_start_unix": 0,
        "month_key": 0,
        "sairen_chapter": [],
        "map_template_by_random_id": {},
        "fleet_ship_ids": [],
        "commander_ids": [],
        "reset_available_at_timestamp": 0,
    }


def save_world_runtime(runtime: dict):
    if runtime.get("map_template_by_random_id") is None:
        runtime["map_template_by_random_id"] = {}
    if runtime.get("sairen_chapter") is None:
        runtime["sairen_chapter"] = []
    upsert_config_entry(WORLD_RUNTIME_CATEGORY, str(runtime["commander_id"]), runtime)


def _current_week_start_unix(now: datetime) -> int:
    offset = _region_offset()
    local_epoch = int(now.timestamp()) + offset
    local_day_start = local_epoch - (local_epoch % 86400)
    weekday = ((local_day_start // 86400) + 4) % 7
    week_start_local = local_day_start - weekday * 86400
    return week_start_local - offset


def _current_month_key(now: datetime) -> int:
    offset = _region_offset()
    local_epoch = int(now.timestamp()) + offset
    dt_utc = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=local_epoch)
    return dt_utc.year * 100 + dt_utc.month


def _load_gameset_key_value(key: str) -> int:
    entry = get_config_entry(WORLD_GAMESET_CATEGORY, key)
    if entry is None:
        entry = get_config_entry(WORLD_GAMESET_CATEGORY_ALT, key)
    if entry is None:
        return 0
    return entry.get("key_value", 0)


def _load_world_move_power_settings():
    max_val = _load_gameset_key_value(WORLD_MOVE_POWER_MAX_KEY)
    if max_val == 0:
        max_val = DEFAULT_WORLD_MOVE_POWER_MAX
    interval = _load_gameset_key_value(WORLD_MOVE_POWER_RECOVERY_KEY)
    if interval == 0:
        interval = DEFAULT_WORLD_MOVE_POWER_RECOVERY
    return max_val, interval


def _apply_world_action_power_regeneration(runtime: dict, now_unix: int, max_power: int, interval: int) -> bool:
    if max_power == 0 or interval == 0:
        return False
    last_recover = runtime.get("last_recover_timestamp", 0)
    if last_recover == 0 or last_recover > now_unix:
        runtime["last_recover_timestamp"] = now_unix
        return True
    action_power = runtime.get("action_power", 0)
    if action_power >= max_power:
        if last_recover == now_unix:
            return False
        runtime["last_recover_timestamp"] = now_unix
        return True
    elapsed = now_unix - last_recover
    ticks = elapsed // interval
    if ticks == 0:
        return False
    missing = max_power - action_power
    gain = ticks
    if gain > missing:
        gain = missing
    runtime["action_power"] = action_power + gain
    runtime["last_recover_timestamp"] = last_recover + gain * interval
    if runtime.get("action_power", 0) >= max_power:
        runtime["last_recover_timestamp"] = now_unix
    return True


def sync_world_runtime(runtime: dict) -> tuple:
    now = datetime.now(timezone.utc)
    now_unix = int(now.timestamp())
    week_start = _current_week_start_unix(now)
    month_key = _current_month_key(now)
    changed = False
    month_reset = False

    if runtime.get("week_start_unix", 0) == 0:
        runtime["week_start_unix"] = week_start
        changed = True
    elif runtime["week_start_unix"] != week_start:
        runtime["week_start_unix"] = week_start
        runtime["stamina_exchange_times"] = 0
        changed = True

    if runtime.get("month_key", 0) == 0:
        runtime["month_key"] = month_key
        changed = True
    elif runtime["month_key"] != month_key:
        runtime["month_key"] = month_key
        runtime["stamina_exchange_times"] = 0
        changed = True
        month_reset = True

    max_power, interval = _load_world_move_power_settings()
    if _apply_world_action_power_regeneration(runtime, now_unix, max_power, interval):
        changed = True

    return changed, month_reset


def build_world_count_info(runtime: dict) -> protobuf.COUNTINFO:
    activate_count = 1 if runtime.get("map_id", 0) > 0 else 0
    msg = protobuf.COUNTINFO()
    msg.step_count = 0
    msg.treasure_count = 0
    msg.task_progress = runtime.get("progress", 0)
    msg.activate_count = activate_count
    del msg.collection_list[:]
    return msg


def get_commander_world_boss_state(commander_id: int) -> Optional[dict]:
    entry = get_config_entry(WORLD_BOSS_STATE_CATEGORY, str(commander_id))
    if entry is None:
        return None
    state = entry
    _ensure_boss_state_defaults(state, commander_id)
    return state


def get_or_create_commander_world_boss_state(commander_id: int) -> dict:
    state = get_commander_world_boss_state(commander_id)
    if state is not None:
        return state
    state = _default_world_boss_state(commander_id)
    save_commander_world_boss_state(state)
    return state


def save_commander_world_boss_state(state: dict):
    _ensure_boss_state_defaults(state, state.get("commander_id", 0))
    upsert_config_entry(WORLD_BOSS_STATE_CATEGORY, str(state["commander_id"]), state)


def _ensure_boss_state_defaults(state: dict, commander_id: int):
    if state.get("commander_id", 0) == 0:
        state["commander_id"] = commander_id
    if "rankings" not in state or state["rankings"] is None:
        state["rankings"] = {}
    if "reward_claimed" not in state or state["reward_claimed"] is None:
        state["reward_claimed"] = {}
    if state.get("next_boss_id", 0) == 0:
        state["next_boss_id"] = 1


def _default_world_boss_state(commander_id: int) -> dict:
    return {
        "commander_id": commander_id,
        "fight_count": 0,
        "fight_count_update_time": 0,
        "self_boss": None,
        "summon_pt": 1,
        "summon_pt_old": 1,
        "summon_pt_daily_acc": 0,
        "summon_pt_old_daily_acc": 0,
        "summon_free": 0,
        "auto_fight_finish_time": 0,
        "default_boss_id": 0,
        "auto_fight_max_damage": 0,
        "guild_support": 0,
        "friend_support": 0,
        "world_support": 0,
        "self_boss_lv": 0,
        "next_boss_id": 1,
        "rankings": {},
        "reward_claimed": {},
        "auto_battle_start_time": 0,
        "auto_battle_boss_id": 0,
    }


def world_boss_state_to_proto(boss: Optional[dict]) -> protobuf.WORLDBOSS_INFO_P34:
    msg = protobuf.WORLDBOSS_INFO_P34()
    if boss is None:
        msg.id = 0
        msg.template_id = 0
        msg.lv = 0
        msg.hp = 0
        msg.owner = 0
        msg.last_time = 0
        msg.kill_time = 0
        msg.fight_count = 0
        msg.rank_count = 0
    else:
        msg.id = boss.get("id", 0)
        msg.template_id = boss.get("template_id", 0)
        msg.lv = boss.get("lv", 0)
        msg.hp = boss.get("hp", 0)
        msg.owner = boss.get("owner", 0)
        msg.last_time = boss.get("last_time", 0)
        msg.kill_time = boss.get("kill_time", 0)
        msg.fight_count = boss.get("fight_count", 0)
        msg.rank_count = boss.get("rank_count", 0)
    return msg
