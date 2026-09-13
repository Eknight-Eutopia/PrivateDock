from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.orm.config_entry import get_config_entry_sync, list_config_entries_sync, upsert_config_entry
from src.orm.resource import consume_resource as _deduct_resource

_NAVAL_ACADEMY_RUNTIME_CATEGORY = "Runtime/naval_academy_runtime.json"

FIELD_MAP = {
    "oilfield_level": "oil_well_level",
    "tradingport_level": "gold_well_level",
    "class_room_level": "class_room_level",
    "shop_street_level": "shop_street_level",
    "skill_room_pos": "skill_room_pos",
}

_UPGRADE_COMPLETE_FIELDS = {
    "oil_well_level": "oil_upgrade_complete_time",
    "gold_well_level": "gold_upgrade_complete_time",
}

_UPGRADE_START_FIELDS = {
    "oil_well_level": "oil_upgrade_start_time",
    "gold_well_level": "gold_upgrade_start_time",
}

_OILFIELD_TEMPLATE_CATEGORY = "ShareCfg/oilfield_template.json"


@dataclass
class NavalAcademyRuntime:
    commander_id: int = 0
    oil_well_level: int = 0
    gold_well_level: int = 0
    oil_collect_timestamp: int = 0
    gold_collect_timestamp: int = 0
    oil_upgrade_start_time: int = 0
    oil_upgrade_complete_time: int = 0
    gold_upgrade_start_time: int = 0
    gold_upgrade_complete_time: int = 0
    class_room_level: int = 1
    shop_street_level: int = 1
    skill_room_pos: int = 0


def load_naval_academy_runtime(commander_id: int) -> Optional[NavalAcademyRuntime]:
    entry = get_config_entry_sync(_NAVAL_ACADEMY_RUNTIME_CATEGORY, str(commander_id))
    if entry is None:
        return None
    data = entry.data
    runtime = NavalAcademyRuntime(
        commander_id=commander_id,
        oil_well_level=data.get("oil_well_level", 0),
        gold_well_level=data.get("gold_well_level", 0),
        oil_collect_timestamp=data.get("oil_collect_timestamp", 0),
        gold_collect_timestamp=data.get("gold_collect_timestamp", 0),
        oil_upgrade_start_time=data.get("oil_upgrade_start_time", 0),
        oil_upgrade_complete_time=data.get("oil_upgrade_complete_time", 0),
        gold_upgrade_start_time=data.get("gold_upgrade_start_time", 0),
        gold_upgrade_complete_time=data.get("gold_upgrade_complete_time", 0),
        class_room_level=data.get("class_room_level", 1),
        shop_street_level=data.get("shop_street_level", 1),
        skill_room_pos=data.get("skill_room_pos", 0),
    )
    runtime.commander_id = commander_id
    return runtime


def load_or_create_naval_academy_runtime(commander_id: int) -> NavalAcademyRuntime:
    runtime = load_naval_academy_runtime(commander_id)
    if runtime is not None:
        return runtime
    return NavalAcademyRuntime(
        commander_id=commander_id,
        oil_well_level=1,
        gold_well_level=1,
    )


def start_academy_upgrade(commander_id: int, effect_str: str) -> bool:
    field = FIELD_MAP.get(effect_str)
    if field is None:
        return False
    complete_field = _UPGRADE_COMPLETE_FIELDS.get(field)
    if complete_field is None:
        runtime = load_or_create_naval_academy_runtime(commander_id)
        current = getattr(runtime, field, 0)
        setattr(runtime, field, current + 1)
        save_naval_academy_runtime(runtime)
        return True

    import time
    now_unix = int(time.time())
    runtime = load_or_create_naval_academy_runtime(commander_id)

    current_complete = getattr(runtime, complete_field, 0)
    if current_complete > now_unix:
        return False

    current_level = getattr(runtime, field, 0)

    template_entry = None
    for candidate in list_config_entries_sync(_OILFIELD_TEMPLATE_CATEGORY):
        if candidate.data and candidate.data.get("level") == current_level:
            template_entry = candidate
            break

    if template_entry is None:
        return False
    upgrade_time = template_entry.data.get("time", 0)
    if upgrade_time <= 0:
        return False

    use = template_entry.data.get("use")
    if use and isinstance(use, list) and len(use) == 2:
        cost_resource_id, cost_amount = use[0], use[1]
        _deduct_resource(commander_id, cost_resource_id, cost_amount)

    start_field = _UPGRADE_START_FIELDS[field]
    setattr(runtime, start_field, now_unix)
    setattr(runtime, complete_field, now_unix + upgrade_time)
    save_naval_academy_runtime(runtime)
    return True


def save_naval_academy_runtime(runtime: NavalAcademyRuntime) -> None:
    if runtime is None:
        raise ValueError("naval academy runtime is None")
    payload = {
        "commander_id": runtime.commander_id,
        "oil_well_level": runtime.oil_well_level,
        "gold_well_level": runtime.gold_well_level,
        "oil_collect_timestamp": runtime.oil_collect_timestamp,
        "gold_collect_timestamp": runtime.gold_collect_timestamp,
        "oil_upgrade_start_time": runtime.oil_upgrade_start_time,
        "oil_upgrade_complete_time": runtime.oil_upgrade_complete_time,
        "gold_upgrade_start_time": runtime.gold_upgrade_start_time,
        "gold_upgrade_complete_time": runtime.gold_upgrade_complete_time,
        "class_room_level": runtime.class_room_level,
        "shop_street_level": runtime.shop_street_level,
        "skill_room_pos": runtime.skill_room_pos,
    }
    upsert_config_entry(_NAVAL_ACADEMY_RUNTIME_CATEGORY, str(runtime.commander_id), payload)
