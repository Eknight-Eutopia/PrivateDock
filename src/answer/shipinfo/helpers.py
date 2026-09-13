
from src.orm.skin import list_owned_ship_shadow_skins as _sync_list_shadows
from src.orm import list_random_flag_ship_phantoms as _sync_list_flags


def _list_random_flag_ship_phantoms(commander_id: int, ship_ids: list) -> dict:
    rows = _sync_list_flags(commander_id, ship_ids)
    result = {}
    for row in rows:
        sid = row.ship_id if hasattr(row, "ship_id") else row[0]
        pid = row.phantom_id if hasattr(row, "phantom_id") else row[1]
        result.setdefault(sid, []).append(pid)
    return result


def _list_owned_ship_shadow_skins(commander_id: int, ship_ids: list) -> dict:
    rows = _sync_list_shadows(commander_id, ship_ids)
    result = {}
    for row in rows:
        sid = row.ship_id if hasattr(row, "ship_id") else row[0]
        result.setdefault(sid, []).append(row)
    return result
