from typing import Optional

from src.connection.client import Client
from src.logger.logger import log_event, LOG_LEVEL_INFO, LOG_LEVEL_ERROR
from src.orm.config_entry import list_config_entries

ACTIVITY_TYPE_REFLUX = 42
RETURN_SIGN_TEMPLATE_CATEGORY = "ShareCfg/return_sign_template.json"
RETURN_PT_TEMPLATE_CATEGORY = "ShareCfg/return_pt_template.json"
ACTIVITY_TEMPLATE_CATEGORY = "ShareCfg/activity_template.json"
REFLUX_ACTIVITY_TABLE = "reflux_activity_config"
REFLUX_PT_ID_CONFIG_KEY = "config_reflux_pt_id"
REFLUX_CHAPTER_CONFIG_KEY = "config_reflux_chapter"


from src.orm.config_entry import entry_data


def _entry_data(entry):
    return entry_data(entry) or {}


def load_reflux_eligibility_config() -> tuple[dict, bool]:
    entries = list_config_entries(ACTIVITY_TEMPLATE_CATEGORY)
    for entry in entries:
        data = _entry_data(entry)
        if data.get("type") != ACTIVITY_TYPE_REFLUX:
            continue
        cfg = _parse_reflux_eligibility_config(data.get("config_data"))
        return cfg, True
    return {}, False


def _parse_reflux_eligibility_config(raw) -> dict:
    if raw is None:
        return {}
    values = raw if isinstance(raw, list) else []
    cfg = {}
    if len(values) >= 1:
        cfg["min_level"] = int(values[0]) if values[0] is not None else 0
    if len(values) >= 2:
        cfg["min_offline_days"] = int(values[1]) if values[1] is not None else 0
    if len(values) >= 3:
        cfg["max_offline_days"] = int(values[2]) if values[2] is not None else 0
    return cfg


def load_return_sign_templates() -> tuple[dict, list]:
    entries = list_config_entries(RETURN_SIGN_TEMPLATE_CATEGORY)
    lookup = {}
    ids = []
    for entry in entries:
        data = _entry_data(entry)
        tid = data.get("id", 0)
        lookup[tid] = data
        ids.append(tid)
    ids.sort()
    return lookup, ids


def load_return_pt_templates() -> tuple[dict, list, int]:
    entries = list_config_entries(RETURN_PT_TEMPLATE_CATEGORY)
    lookup = {}
    ids = []
    pt_item_id = 0
    for entry in entries:
        data = _entry_data(entry)
        tid = data.get("id", 0)
        lookup[tid] = data
        ids.append(tid)
        if pt_item_id == 0:
            pt_item_id = data.get("virtual_item", 0)
    ids.sort()
    return lookup, ids, pt_item_id


def select_level_index(level: int, ranges: list) -> tuple[int, Optional[Exception]]:
    for i, entry in enumerate(ranges):
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        if entry[0] <= level <= entry[1]:
            return i, None
    return -1, Exception(f"no level range for {level}")


def build_award_drops(display: list) -> list:
    drops = []
    for entry in display:
        if not isinstance(entry, (list, tuple)) or len(entry) < 3:
            raise Exception("award display entry missing fields")
        drops.append({"type": int(entry[0]), "id": int(entry[1]), "number": int(entry[2])})
    return drops


def ensure_commander_loaded(client: Client, scope: str) -> Optional[Exception]:
    c = client.commander
    if c is None:
        return Exception("commander not loaded")
    try:
        _ = c.get_item_count
        _ = c.get_resource_count
    except Exception:
        pass
    log_event(scope, "Load", "commander maps missing, reloading commander", LOG_LEVEL_INFO)
    try:
        c.load()
    except Exception as e:
        log_event(scope, "Load", "commander load failed", LOG_LEVEL_ERROR)
        return e
    return None


def is_same_day(a: int, b: int) -> bool:
    if a == 0 or b == 0:
        return False
    import datetime
    day_a = datetime.datetime.utcfromtimestamp(a)
    day_b = datetime.datetime.utcfromtimestamp(b)
    return day_a.year == day_b.year and day_a.month == day_b.month and day_a.day == day_b.day


def is_reflux_expired(return_time: int, sign_days: int, now: int) -> bool:
    if return_time == 0 or sign_days == 0:
        return False
    return return_time + sign_days * 86400 <= now


def is_reflux_eligible(client: Client, cfg: dict, now: float) -> bool:
    min_level = cfg.get("min_level", 0)
    if min_level > 0 and client.commander and client.commander.level < min_level:
        return False
    prev = client.previous_login_at
    if prev is None:
        return False
    if now < prev:
        return False
    offline_seconds = now - prev
    if offline_seconds < 0:
        return False
    offline_days = int(offline_seconds // 86400)
    min_offline = cfg.get("min_offline_days", 0)
    if offline_days < min_offline:
        return False
    max_offline = cfg.get("max_offline_days", 0)
    if max_offline > 0 and offline_days > max_offline:
        return False
    return True


def get_pt_item_id_from_activity(activity_id: int) -> int:
    config = load_reflux_activity_config(activity_id)
    if config is None:
        return 0
    pt_config = config.get(REFLUX_PT_ID_CONFIG_KEY, {})
    if isinstance(pt_config, list) and len(pt_config) > 0:
        pt_list = pt_config
    elif isinstance(pt_config, dict):
        pt_list = list(pt_config.values())
    else:
        return 0
    item_id = pt_list[0] if pt_list else 0
    if isinstance(item_id, (int, float)):
        return int(item_id)
    if isinstance(item_id, dict):
        return int(item_id.get("id", 0))
    return 0


def get_chapter_config_id_from_activity(activity_id: int) -> int:
    config = load_reflux_activity_config(activity_id)
    if config is None:
        return 0
    chapter_config = config.get(REFLUX_CHAPTER_CONFIG_KEY, 0)
    if isinstance(chapter_config, (int, float)):
        return int(chapter_config)
    return 0


def load_reflux_activity_config(activity_id: int):
    from src.orm.config_entry import get_config_entry
    try:
        entry = get_config_entry(REFLUX_ACTIVITY_TABLE, str(activity_id))
        if isinstance(entry, dict):
            return entry
        if hasattr(entry, "data"):
            return entry.data
    except Exception:
        pass
    return None
