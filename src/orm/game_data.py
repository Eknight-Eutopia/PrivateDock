from __future__ import annotations
from typing import Optional

from sqlalchemy import select

from src.db.session import get_sync_session
from src.logger.logger import LOG_LEVEL_ERROR, log_event
from src.orm.config_entry import get_config_entry_sync, get_config_entries_sync
from src.orm.ship_data_blueprint_config import ShipDataBlueprintConfig
from src.orm.ship_strengthen_blueprint_config import ShipStrengthenBlueprintConfig
from src.orm.technology_catchup_item import TechnologyCatchupItem


def get_ship_breakout_config(ship_id: int):
    from src.orm.ship_breakout_config import get_ship_breakout_config as _load
    return _load(ship_id)


# Static game data (ship_data_template.json is imported once, never written at
# runtime) -- safe to cache for the process lifetime. The dock sync used to run
# one sync session PER SHIP (skill_ids + equip slots); with the warm cache the
# whole dock needs one batched SELECT (see preload_ship_template_configs).
_SHIP_TEMPLATE_CACHE: dict[int, object | None] = {}


def _get_ship_template_cached(ship_id: int):
    if ship_id not in _SHIP_TEMPLATE_CACHE:
        entry = get_config_entry_sync("sharecfgdata/ship_data_template.json", str(ship_id))
        _SHIP_TEMPLATE_CACHE[ship_id] = entry.data if entry is not None else None
    return _SHIP_TEMPLATE_CACHE[ship_id]


def preload_ship_template_configs(ship_ids: list) -> None:
    missing = [s for s in dict.fromkeys(int(i) for i in ship_ids) if s not in _SHIP_TEMPLATE_CACHE]
    if not missing:
        return
    entries = get_config_entries_sync("sharecfgdata/ship_data_template.json", [str(s) for s in missing])
    for sid in missing:
        entry = entries.get(str(sid))
        _SHIP_TEMPLATE_CACHE[sid] = entry.data if entry is not None else None


def get_ship_equip_config(ship_id: int):
    data = _get_ship_template_cached(ship_id)
    if data is None:
        log_event("ORM", "Game_data", f"get_ship_equip_config entry is None for ship_id: {ship_id}", LOG_LEVEL_ERROR)
        return None
    return data

def _get_ship_equip_slot_count(equip_data) -> int:
    if not isinstance(equip_data, dict):
        return 3
    slot_keys = ["equip_1", "equip_2", "equip_3", "equip_4", "equip_5"]
    count = 0
    for i, key in enumerate(slot_keys):
        if equip_data.get(key):
            count = i + 1
    return count if count > 0 else 3


def get_ship_template_config(ship_id: int):
    data = _get_ship_template_cached(ship_id)
    if data is None:
        log_event("ORM", "Game_data", f"get_ship_template_config entry is None for ship_id: {ship_id}", LOG_LEVEL_ERROR)
        return None
    return data


def get_ship_skill_ids(ship_id: int) -> list:
    data = _get_ship_template_cached(ship_id)
    if not isinstance(data, dict):
        return []
    display = data.get("buff_list_display") or []
    buff_list = data.get("buff_list") or []
    return [sid for sid in display if sid in buff_list]


def get_ship_strengthen_config(strengthen_id: int):
    from src.orm.config_entry import get_config_entry_sync
    entry = get_config_entry_sync("ShareCfg/ship_data_strengthen.json", str(strengthen_id))
    if entry is None:
        log_event("ORM", "Game_data", f"get_ship_strengthen_config entry is None for strengthen_id: {strengthen_id}", LOG_LEVEL_ERROR)
        return None
    return entry.data


def get_ship_strengthen_blueprint_config(ship_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(ShipStrengthenBlueprintConfig).where(
                ShipStrengthenBlueprintConfig.ship_id == ship_id
            )
        )
        return result.scalar_one_or_none()


def get_ship_data_blueprint_config(ship_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(ShipDataBlueprintConfig).where(
                ShipDataBlueprintConfig.ship_id == ship_id
            )
        )
        return result.scalar_one_or_none()


def get_compose_data_template_entry(template_id: int):
    from src.orm.config_entry import get_config_entry_sync
    entry = get_config_entry_sync("ShareCfg/compose_data_template.json", str(template_id))
    return entry.data if entry else None


def get_transform_data_template(template_id: int):
    from src.orm.config_entry import get_config_entry_sync
    entry = get_config_entry_sync("ShareCfg/transform_data_template.json", str(template_id))
    return entry.data if entry else None


def get_equip_upgrade_data(equip_id: int):
    from src.orm.config_entry import get_config_entry_sync
    entry = get_config_entry_sync("ShareCfg/equip_upgrade_data.json", str(equip_id))
    return entry.data if entry else None


def find_ship_equipment(ship_id: int):
    from src.orm.config_entry import get_config_entry_sync
    entry = get_config_entry_sync("sharecfgdata/ship_data_template.json", str(ship_id))
    return entry.data if entry is not None else None


def resolve_equipment_config(config_row):
    return config_row


def get_sp_weapon_data_statistics_config(spweapon_id: int) -> Optional[dict]:
    entry = get_config_entry_sync("sharecfgdata/spweapon_data_statistics.json", str(spweapon_id))
    if entry and entry.data:
        return entry.data
    try:
        from src.misc.update_data_helpers import get_privatedock_data
        data = get_privatedock_data("EN", "sharecfgdata/spweapon_data_statistics.json")
        if isinstance(data, dict):
            return data.get(str(spweapon_id))
    except Exception:
        pass
    return None


def get_sp_weapon_upgrade_config(upgrade_id: int) -> Optional[dict]:
    entry = get_config_entry_sync("ShareCfg/spweapon_upgrade.json", str(upgrade_id))
    if entry and entry.data:
        return entry.data
    try:
        from src.misc.update_data_helpers import get_privatedock_data
        data = get_privatedock_data("EN", "ShareCfg/spweapon_upgrade.json")
        if isinstance(data, dict):
            return data.get(str(upgrade_id))
        elif isinstance(data, list):
            for row in data:
                if isinstance(row, dict) and row.get("id") == upgrade_id:
                    return row
    except Exception:
        pass
    return None


def get_technology_catchup_item(catchup_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(TechnologyCatchupItem).where(
                TechnologyCatchupItem.catchup_id == catchup_id
            )
        )
        return result.scalar_one_or_none()
