import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .atelier_shared import (
    ATELIER_RESULT_SUCCESS,
    ATELIER_RESULT_MALFORMED_REQUEST,
    ATELIER_RESULT_INVALID_ACTIVITY,
    ATELIER_RESULT_INVALID_RECIPE_OR_ITEM,
    ATELIER_RESULT_STORAGE_FAILURE,
    ensure_atelier_activity,
    parse_atelier_item_config,
    atelier_item_buff_tier_count,
)


def handle_atelier_refresh_buff(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 26056
    payload = protobuf.CS_26055()
    payload.ParseFromString(buffer)

    response = protobuf.SC_26056(result=ATELIER_RESULT_MALFORMED_REQUEST)

    try:
        ensure_atelier_activity(payload.act_id)
    except Exception:
        response.result = ATELIER_RESULT_INVALID_ACTIVITY
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    next_slots, result = _validate_atelier_buff_slots(payload.slots)
    if result != ATELIER_RESULT_SUCCESS:
        response.result = result
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    from src.orm.backyard import lock_atelier_state, get_or_create_atelier_state, save_atelier_state

    try:
        lock_atelier_state(client.commander.commander_id, payload.act_id)
        state = get_or_create_atelier_state(client.commander.commander_id, payload.act_id)

        if isinstance(state, dict):
            items = state.get("items", {})
            if not _atelier_has_buff_slot_items(items, next_slots):
                response.result = ATELIER_RESULT_INVALID_RECIPE_OR_ITEM
                asyncio.create_task(client.send_message(packet_id, response))
                return 0, packet_id, None

            state["slots"] = next_slots
            save_atelier_state(state)
            response.result = ATELIER_RESULT_SUCCESS
    except Exception:
        response.result = ATELIER_RESULT_STORAGE_FAILURE

    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _validate_atelier_buff_slots(slots) -> tuple:
    next_slots = {}
    for pos in range(1, 6):
        next_slots[pos] = {"pos": pos, "item_id": 0, "item_num": 0}

    seen_pos = set()
    seen_item = set()

    for slot in slots:
        pos = slot.pos
        if pos < 1 or pos > 5:
            return None, ATELIER_RESULT_MALFORMED_REQUEST
        if pos in seen_pos:
            return None, ATELIER_RESULT_MALFORMED_REQUEST
        seen_pos.add(pos)

        item_id = slot.itemid
        item_num = slot.itemnum

        if item_id == 0:
            if item_num != 0:
                return None, ATELIER_RESULT_MALFORMED_REQUEST
            next_slots[pos] = {"pos": pos, "item_id": 0, "item_num": 0}
            continue

        if item_id in seen_item:
            return None, ATELIER_RESULT_MALFORMED_REQUEST

        try:
            item_config = parse_atelier_item_config(item_id)
        except Exception:
            return None, ATELIER_RESULT_INVALID_RECIPE_OR_ITEM

        tier_count = atelier_item_buff_tier_count(item_config)
        if tier_count == 0:
            return None, ATELIER_RESULT_INVALID_RECIPE_OR_ITEM
        if item_num == 0 or item_num > tier_count:
            return None, ATELIER_RESULT_MALFORMED_REQUEST

        seen_item.add(item_id)
        next_slots[pos] = {"pos": pos, "item_id": item_id, "item_num": item_num}

    return next_slots, ATELIER_RESULT_SUCCESS


def _atelier_has_buff_slot_items(items: dict, slots: dict) -> bool:
    for pos in range(1, 6):
        slot = slots.get(pos, {})
        item_id = slot.get("item_id", 0)
        if item_id == 0:
            continue
        if items.get(item_id, 0) == 0:
            return False
    return True
