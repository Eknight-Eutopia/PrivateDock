from typing import Optional

from src.db.store import get_default_store


from src.orm.ship_data_statistics_config import get_ship_base_skin_id


def get_technology_shadow_unlock_config(shadow_id: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry_sync
    from src.db.store import decode_json_value
    entry = get_config_entry_sync("ShareCfg/technology_shadow_unlock.json", str(shadow_id))
    if entry is None or not entry.data:
        return None
    data = decode_json_value(entry.data) if not isinstance(entry.data, dict) else entry.data
    return {
        "id": data.get("id", shadow_id),
        "type": data.get("type", 0),
        "target_num": data.get("target_num", 0),
        "shadow_id": shadow_id,
        "skin_id": data.get("skin_id", 0),
    }


def list_owned_ship_shadow_skins(commander_id: int, ship_ids: list[int]) -> dict[int, list[dict]]:
    store = get_default_store()
    if store is None:
        return {}
    rows = store.fetch(
        "SELECT ship_id, shadow_id, skin_id FROM owned_ship_shadow_skins WHERE commander_id = $1 AND ship_id = ANY($2)",
        commander_id, ship_ids
    )
    result: dict[int, list[dict]] = {}
    for row in rows:
        sid = row["ship_id"]
        if sid not in result:
            result[sid] = []
        result[sid].append({
            "shadow_id": row["shadow_id"],
            "skin_id": row["skin_id"],
        })
    return result


def upsert_owned_ship_shadow_skin(commander_id: int, ship_id: int, shadow_id: int, skin_id: int) -> bool:
    store = get_default_store()
    if store is None:
        return False
    try:
        store.execute(
            "INSERT INTO owned_ship_shadow_skins (commander_id, ship_id, shadow_id, skin_id) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT (commander_id, ship_id, shadow_id) DO UPDATE SET skin_id = $4",
            commander_id, ship_id, shadow_id, skin_id
        )
        return True
    except Exception:
        return False
