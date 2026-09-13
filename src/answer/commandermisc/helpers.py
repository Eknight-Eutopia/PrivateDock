import json

from src.orm.global_skin_restriction import list_global_skin_restrictions as _sync_list_skin_restrictions
from src.orm.global_skin_restriction_window import list_global_skin_restriction_windows as _sync_list_skin_windows
from src.orm.skin import list_owned_ship_shadow_skins as _sync_list_shadow_skins
from src.orm import list_config_entries as _sync_list_config_entries, list_random_flag_ship_phantoms as _sync_list_flag_phantoms


def list_config_entries(category: str) -> list:
    rows = _sync_list_config_entries(category)
    result = []
    for row in rows:
        data = row.data
        if isinstance(data, str):
            result.append(json.loads(data))
        elif isinstance(data, (bytes, bytearray)):
            result.append(json.loads(data.decode("utf-8")))
        else:
            result.append(data)
    return result


def list_global_skin_restrictions() -> list:
    return _sync_list_skin_restrictions()


def list_global_skin_restriction_windows() -> list:
    return _sync_list_skin_windows()


def list_random_flag_ship_phantoms(commander_id: int, ship_ids: list) -> dict:
    rows = _sync_list_flag_phantoms(commander_id)
    result = {}
    ship_set = set(ship_ids)
    for row in rows:
        if row.ship_id in ship_set:
            result.setdefault(row.ship_id, []).append(row.phantom_id)
    return result


def list_owned_ship_shadow_skins(commander_id: int, ship_ids: list) -> dict:
    rows = _sync_list_shadow_skins(commander_id)
    result = {}
    ship_set = set(ship_ids)
    for row in rows:
        if row.ship_id in ship_set:
            result.setdefault(row.ship_id, []).append({"shadow_id": row.shadow_id, "skin_id": row.skin_id})
    return result
