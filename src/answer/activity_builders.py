import json
import time
from typing import Any, Optional

from src.answer.activity_templates import ActivityTemplate
from src.answer.activity_constants import (
    ACTIVITY_TYPE_BOSS_BATTLE_MARK_2,
    ACTIVITY_TYPE_PUZZLE,
    ACTIVITY_TYPE_PUZZLE_CONNECT,
    ACTIVITY_TYPE_TASKS,
    ACTIVITY_TYPE_NEW_SERVER_TASK,
    ACTIVITY_TYPE_TOWN,
)


def activity_stop_time(raw: Any) -> int:
    if raw is None:
        return 0
    if isinstance(raw, str):
        return 0
    if not isinstance(raw, list) or len(raw) < 3:
        return 0
    if not isinstance(raw[0], str) or raw[0] != "timer":
        return 0
    end = raw[2]
    if not isinstance(end, list) or len(end) != 2:
        return 0
    date = end[0]
    clock = end[1]
    if not isinstance(date, list) or len(date) != 3:
        return 0
    if not isinstance(clock, list) or len(clock) != 3:
        return 0
    try:
        from datetime import datetime, timezone
        dt = datetime(int(date[0]), int(date[1]), int(date[2]),
                       int(clock[0]), int(clock[1]), int(clock[2]),
                       tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return 0


def build_activity_info(template: ActivityTemplate, stop_time: int) -> Optional[dict]:
    if template.type == ACTIVITY_TYPE_PUZZLE:
        if not _validate_puzzle_activity(template.id):
            return None
    if template.type == ACTIVITY_TYPE_PUZZLE_CONNECT:
        if not _validate_activity_time(template.time):
            return None
    if template.type == ACTIVITY_TYPE_TASKS:
        if not _validate_task_activity(template.config_data):
            return None
    if template.type == ACTIVITY_TYPE_NEW_SERVER_TASK:
        if not _validate_new_server_task_activity(template.config_data):
            return None

    info = _base_activity_info(template, stop_time)
    if template.type == ACTIVITY_TYPE_TOWN:
        return _build_town_activity_info(info)
    if template.type == ACTIVITY_TYPE_BOSS_BATTLE_MARK_2:
        return _build_boss_battle_mark_2_activity_info(info)
    return info


def _base_activity_info(template: ActivityTemplate, stop_time: int) -> dict:
    return {
        "id": template.id,
        "stop_time": stop_time,
        "data1_list": [],
        "data2_list": [],
        "data3_list": [],
        "data4_list": [],
        "date1_key_value_list": [],
        "group_list": [],
        "collection_list": [],
        "task_list": [],
        "buff_list": [],
    }


def _build_town_activity_info(info: dict) -> dict:
    town_level = 1
    level_cfg = _load_town_level_config(town_level)
    start_time = int(time.time())
    workplaces = []
    if level_cfg and level_cfg.get("unlock_work"):
        workplaces = [
            {"key": wid, "value": start_time}
            for wid in level_cfg["unlock_work"][0]
        ]
    info["data1"] = 0
    info["data2"] = town_level
    info["date1_key_value_list"].append({
        "key": 1,
        "value_list": workplaces,
    })
    return info


def _build_boss_battle_mark_2_activity_info(info: dict) -> dict:
    info["date1_key_value_list"].append({
        "key": 1,
        "value_list": [],
    })
    info["date1_key_value_list"].append({
        "key": 2,
        "value_list": [],
    })
    return info


def build_level_award_data1_list(config_id: int, claimed_level: int) -> list:
    """Claimed level-award thresholds.

    The client greys out awards whose level threshold is present in
    ACTIVITYINFO.data1_list (LevelAwardPage.OnUpdateFlush and
    Activity.IsNeedShowTip for ACTIVITY_TYPE_LEVELAWARD). The claimed
    threshold is persisted as store_state.data1 (highest claimed level,
    since claims are sequential: t <= claimed_level is rejected), so the
    list is every front_drops threshold not exceeding that level.
    """
    if claimed_level <= 0:
        return []
    from src.orm.config_entry import get_config_entry
    try:
        raw = get_config_entry("ShareCfg/activity_level_award.json", str(config_id))
    except (ImportError, Exception):
        return []
    if raw is None:
        return []
    data = raw.data if hasattr(raw, "data") else raw
    front_drops = data.get("front_drops", []) if isinstance(data, dict) else []
    levels = []
    for entry in front_drops:
        if not isinstance(entry, list) or len(entry) < 1:
            continue
        threshold = entry[0]
        if not isinstance(threshold, (int, float)):
            continue
        threshold = int(threshold)
        if threshold <= claimed_level:
            levels.append(threshold)
    return levels


def _load_town_level_config(level: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry
    try:
        raw = get_config_entry("ShareCfg/activity_town_level.json", str(level))
        return raw
    except (ImportError, Exception):
        return None


def _validate_puzzle_activity(activity_id: int) -> bool:
    return _config_entry_exists("ShareCfg/activity_event_picturepuzzle.json", str(activity_id))


def _validate_new_server_task_activity(config_data: Any) -> bool:
    if config_data is None:
        return False
    try:
        data = json.loads(config_data) if isinstance(config_data, str) else config_data
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(data, list):
        return False
    for group in data:
        if not isinstance(group, list):
            return False
        for task_id in group:
            if not _config_entry_exists("ShareCfg/task_data_template.json", str(int(task_id))):
                return False
    return True


def _validate_activity_time(config: Any) -> bool:
    if config is None:
        return False
    try:
        data = json.loads(config) if isinstance(config, str) else config
    except (json.JSONDecodeError, TypeError):
        return False
    if isinstance(data, list):
        return len(data) >= 2
    if isinstance(data, str):
        if data == "stop":
            return False
    return False


def _validate_task_activity(config_data: Any) -> bool:
    if config_data is None:
        return False
    ids = _parse_activity_task_ids(config_data)
    if ids is None:
        return False
    for task_id in ids:
        if not _config_entry_exists("ShareCfg/task_data_template.json", str(task_id)):
            return False
    return True


def _parse_activity_task_ids(config_data: Any) -> Optional[list]:
    try:
        data = json.loads(config_data) if isinstance(config_data, str) else config_data
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
        return [int(x) for x in data]
    if isinstance(data, list):
        ids = []
        for item in data:
            if isinstance(item, (int, float)):
                ids.append(int(item))
            elif isinstance(item, list):
                for nested in item:
                    ids.append(int(nested))
            else:
                return None
        return ids
    return None


def _config_entry_exists(category: str, key: str) -> bool:
    from src.db.store import NotFoundError
    from src.orm.config_entry import get_config_entry
    try:
        get_config_entry(category, key)
        return True
    except NotFoundError:
        return False
    except Exception:
        return False
