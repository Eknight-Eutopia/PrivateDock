import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .atelier_shared import (
    ATELIER_RESULT_SUCCESS,
    ATELIER_RESULT_MALFORMED_REQUEST,
    ATELIER_RESULT_INVALID_ACTIVITY,
    ATELIER_RESULT_INVALID_RECIPE_OR_ITEM,
    ATELIER_RESULT_INSUFFICIENT_ITEMS,
    ATELIER_RESULT_RECIPE_LIMIT_REACHED,
    ATELIER_RESULT_STORAGE_FAILURE,
    ensure_atelier_activity,
    parse_atelier_recipe_config,
    parse_atelier_recipe_allowed_items,
)


def handle_atelier_composite(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 26054
    payload = protobuf.CS_26053()
    payload.ParseFromString(buffer)

    response = protobuf.SC_26054(result=ATELIER_RESULT_MALFORMED_REQUEST)

    try:
        ensure_atelier_activity(payload.act_id)
    except Exception:
        response.result = ATELIER_RESULT_INVALID_ACTIVITY
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    try:
        recipe = parse_atelier_recipe_config(payload.recipe_id)
    except Exception:
        response.result = ATELIER_RESULT_INVALID_RECIPE_OR_ITEM
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    times = payload.times
    if times == 0:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    request_items = _parse_atelier_request_items(payload.items, times)
    if not request_items:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    try:
        allowed_items = parse_atelier_recipe_allowed_items(recipe)
    except Exception:
        response.result = ATELIER_RESULT_INVALID_RECIPE_OR_ITEM
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    if allowed_items:
        for item_id in request_items:
            if item_id not in allowed_items:
                response.result = ATELIER_RESULT_INVALID_RECIPE_OR_ITEM
                asyncio.create_task(client.send_message(packet_id, response))
                return 0, packet_id, None

    rewards = _build_atelier_recipe_rewards(recipe, times)
    if not rewards:
        response.result = ATELIER_RESULT_INVALID_RECIPE_OR_ITEM
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    from src.orm.backyard import lock_atelier_state, get_or_create_atelier_state, save_atelier_state

    try:
        lock_atelier_state(client.commander.commander_id, payload.act_id)
        state = get_or_create_atelier_state(client.commander.commander_id, payload.act_id)

        if isinstance(state, dict):
            item_num = recipe.get("item_num", 0)
            if item_num > 0:
                recipe_uses = state.get("recipe_uses", {})
                current_uses = recipe_uses.get(recipe.get("id", 0), 0)
                if current_uses + times > item_num:
                    response.result = ATELIER_RESULT_RECIPE_LIMIT_REACHED
                    asyncio.create_task(client.send_message(packet_id, response))
                    return 0, packet_id, None

            items = state.get("items", {})
            for item_id, count in request_items.items():
                if items.get(item_id, 0) < count:
                    response.result = ATELIER_RESULT_INSUFFICIENT_ITEMS
                    asyncio.create_task(client.send_message(packet_id, response))
                    return 0, packet_id, None

            for item_id, count in request_items.items():
                items[item_id] = items.get(item_id, 0) - count
                if items[item_id] == 0:
                    del items[item_id]

            recipe_uses = state.get("recipe_uses", {})
            recipe_uses[recipe.get("id", 0)] = recipe_uses.get(recipe.get("id", 0), 0) + times

            award_list = _apply_atelier_rewards(state, rewards)
            for item in award_list:
                entry = protobuf.DROPINFO()
                entry.type = item.get("type", 0)
                entry.id = item.get("id", 0)
                entry.number = item.get("number", 0)
                response.award_list.append(entry)

            save_atelier_state(state)
            response.result = ATELIER_RESULT_SUCCESS
            # Server-authoritative task progress: crafting augment modules
            # advances "Craft any Augment Module N time(s)" (sub_type 200).
            try:
                from src.answer.task_handlers import schedule_emit
                schedule_emit(client, 200, 0, times)
            except Exception:
                pass
    except Exception:
        response.result = ATELIER_RESULT_STORAGE_FAILURE

    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _parse_atelier_request_items(items, times: int) -> dict:
    if times == 0:
        return None
    item_map = {}
    for item in items:
        key = item.key
        value = item.value
        if key == 0 or value == 0:
            return None
        scaled = value * times
        item_map[key] = item_map.get(key, 0) + scaled
    return item_map


def _build_atelier_recipe_rewards(recipe: dict, times: int) -> list:
    item_id = recipe.get("item_id", [])
    if len(item_id) < 2 or times == 0:
        return None
    count = times
    if count == 0:
        return None
    return [{"drop_type": item_id[0], "drop_id": item_id[1], "count": count}]


def _apply_atelier_rewards(state: dict, rewards: list) -> list:
    award_map = {}
    for reward in rewards:
        drop_type = reward.get("drop_type", 0)
        drop_id = reward.get("drop_id", 0)
        count = reward.get("count", 0)
        if drop_type == 0 or drop_id == 0 or count == 0:
            continue
        _apply_atelier_reward_single(state, reward)
        key = f"{drop_type}:{drop_id}"
        if key in award_map:
            award_map[key]["number"] = award_map[key].get("number", 0) + count
        else:
            award_map[key] = {"type": drop_type, "id": drop_id, "number": count}

    lst = list(award_map.values())
    lst.sort(key=lambda x: (x.get("type", 0), x.get("id", 0)))
    return lst


def _apply_atelier_reward_single(state: dict, reward: dict) -> None:
    drop_type = reward.get("drop_type", 0)
    drop_id = reward.get("drop_id", 0)
    count = reward.get("count", 0)

    if drop_type == 18:
        items = state.setdefault("items", {})
        items[drop_id] = items.get(drop_id, 0) + count
