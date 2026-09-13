from typing import Optional, Tuple

from src.orm.commander_home import get_commander_home as _sync_get_commander_home, ensure_commander_home as _sync_ensure_commander_home, update_commander_home_slot as _sync_update_home_slot, update_commander_home as _sync_update_home, clear_commander_home_cache_exp as _sync_clear_cache_exp
from src.orm.config_entry import fetch_config_entries_data, fetch_config_entry_data


get_config_entry = fetch_config_entry_data
list_config_entries = fetch_config_entries_data


def ensure_commander_home(commander_id: int) -> Tuple[dict, list]:
    return _sync_ensure_commander_home(commander_id)


def get_commander_home(commander_id: int) -> Tuple[Optional[dict], list]:
    return _sync_get_commander_home(commander_id)


def update_commander_home_slot(slot: dict) -> None:
    _sync_update_home_slot(slot)


def update_commander_home(home: dict) -> None:
    _sync_update_home(home)


def clear_commander_home_cache_exp(commander_id: int) -> None:
    _sync_clear_cache_exp(commander_id)


def get_commander_home_feed_exp(level: int) -> int:
    cfg = _load_commander_home_level_config(level)
    if len(cfg.get("feed_level", [])) < 2:
        return 0
    return cfg["feed_level"][1]


def get_commander_home_style_list(level: int) -> list:
    cfg = _load_commander_home_level_config(level)
    styles = cfg.get("nest_appearance", [])
    if not styles:
        return [1]
    return styles


def _load_commander_home_slot_count() -> int:
    entry = get_config_entry("ShareCfg/gameset.json", "commander_home_number")
    if entry is None:
        return 4
    key_value = entry.get("key_value", 0)
    if key_value == 0:
        return 4
    return key_value


def _load_commander_home_level_config(level: int) -> dict:
    entry = get_config_entry("ShareCfg/commander_home.json", str(level))
    if entry is None:
        return {}
    return entry
