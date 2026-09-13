import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .atelier_shared import (
    ATELIER_RESULT_SUCCESS,
    ATELIER_RESULT_INVALID_ACTIVITY,
    ATELIER_RESULT_STORAGE_FAILURE,
    ensure_atelier_activity,
    sorted_atelier_kvdata,
    sorted_atelier_slots,
)


def handle_atelier_request(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 26052
    payload = protobuf.CS_26051()
    payload.ParseFromString(buffer)

    result = ATELIER_RESULT_SUCCESS
    state = {"items": {}, "recipe_uses": {}, "slots": {}}

    try:
        ensure_atelier_activity(payload.act_id)
    except Exception:
        result = ATELIER_RESULT_INVALID_ACTIVITY
    else:
        from src.orm.backyard import get_or_create_atelier_state
        try:
            loaded = get_or_create_atelier_state(client.commander.commander_id, payload.act_id)
            if loaded:
                state = loaded
        except Exception:
            result = ATELIER_RESULT_STORAGE_FAILURE

    response = protobuf.SC_26052(result=result)
    items_data = sorted_atelier_kvdata(state.get("items", {}) if isinstance(state, dict) else {})
    for item in items_data:
        entry = protobuf.KVDATA()
        entry.key = item.get("key", 0)
        entry.value = item.get("value", 0)
        response.items.append(entry)
    recipes_data = sorted_atelier_kvdata(state.get("recipe_uses", {}) if isinstance(state, dict) else {})
    for item in recipes_data:
        entry = protobuf.KVDATA()
        entry.key = item.get("key", 0)
        entry.value = item.get("value", 0)
        response.recipes.append(entry)
    slots_data = sorted_atelier_slots(state.get("slots", {}) if isinstance(state, dict) else {})
    for item in slots_data:
        entry = protobuf.BUFF_SLOT()
        entry.pos = item.get("pos", 0)
        entry.itemid = item.get("itemid", 0)
        entry.itemnum = item.get("itemnum", 0)
        response.slots.append(entry)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
