from typing import Optional

from src.db.store import get_default_store

CREATE_PLAYER_NAME_MIN = 4
CREATE_PLAYER_NAME_MAX = 14

STARTER_SHIP_IDS = {101171, 201211, 401231}


async def get_device_auth_map(device_id: str) -> Optional[dict]:
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT device_id, arg2, account_id FROM device_auth_maps WHERE device_id = $1",
        device_id
    )
    if row is None:
        return None
    return {"device_id": row["device_id"], "arg2": row["arg2"], "account_id": row["account_id"]}


async def get_yostarus_map_by_arg2(arg2: int) -> Optional[dict]:
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT arg2, account_id FROM yostarus_maps WHERE arg2 = $1",
        arg2
    )
    if row is None:
        return None
    return {"arg2": row["arg2"], "account_id": row["account_id"]}


async def check_commander_name_availability(name: str) -> Optional[str]:
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT commander_id FROM commanders WHERE name = $1",
        name
    )
    if row is not None:
        return "name_exists"
    return None


async def upsert_device_auth_map(device_id: str, arg2: int, account_id: int) -> None:
    store = get_default_store()
    await store.aexecute(
        "INSERT INTO device_auth_maps (device_id, arg2, account_id) VALUES ($1, $2, $3) "
        "ON CONFLICT (device_id) DO UPDATE SET arg2 = EXCLUDED.arg2, account_id = EXCLUDED.account_id",
        device_id, arg2, account_id
    )
