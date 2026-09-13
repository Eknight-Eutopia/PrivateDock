import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .helpers import (
    get_technology_shadow_unlock_config,
    get_ship_base_skin_id,
    list_owned_ship_shadow_skins,
    upsert_owned_ship_shadow_skin,
)


def handle_finish_phantom_quest(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12210()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12211, e

    response = protobuf.SC_12211()
    response.result = 0
    ship_id = payload.ship_id
    shadow_id = payload.skin_shadow_id

    owned_ships_map = getattr(client.commander, "owned_ships_map", {}) or {}
    if ship_id not in owned_ships_map:
        response.result = 1
        asyncio.create_task(client.send_message(12211, response))
        return 0, 12211, None

    quest = get_technology_shadow_unlock_config(shadow_id)
    if quest is None:
        response.result = 1
        asyncio.create_task(client.send_message(12211, response))
        return 0, 12211, None

    skin_id = get_ship_base_skin_id(owned_ships_map[ship_id].get("ship_id", ship_id))
    if skin_id == 0:
        response.result = 1
        asyncio.create_task(client.send_message(12211, response))
        return 0, 12211, None

    commander_id = getattr(client.commander, "commander_id", 0)
    owned_skins = list_owned_ship_shadow_skins(commander_id, [ship_id])
    for existing in owned_skins.get(ship_id, []):
        if existing["shadow_id"] != shadow_id:
            continue
        if existing["skin_id"] != skin_id:
            if not upsert_owned_ship_shadow_skin(commander_id, ship_id, shadow_id, skin_id):
                response.result = 1
        asyncio.create_task(client.send_message(12211, response))
        return 0, 12211, None

    if quest.get("type") == 5:
        target_num = quest.get("target_num", 0)
        if hasattr(client.commander, "consume_resource"):
            try:
                client.commander.consume_resource(4, target_num)
            except Exception:
                response.result = 1
                asyncio.create_task(client.send_message(12211, response))
                return 0, 12211, None

    if not upsert_owned_ship_shadow_skin(commander_id, ship_id, shadow_id, skin_id):
        response.result = 1

    asyncio.create_task(client.send_message(12211, response))
    return 0, 12211, None


def handle_get_phantom_quest_progress(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12212()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12213, e

    response = protobuf.SC_12213()
    from src.protobuf import protobuf as pb
    ship_ids = list(payload.ship_id_list) if payload.ship_id_list else []
    if ship_ids:
        del response.ship_count_list[:]
        for ship_id in ship_ids:
            item = pb.KVDATA()
            item.key = ship_id
            item.value = 0
            response.ship_count_list.append(item)

    asyncio.create_task(client.send_message(12213, response))
    return 0, 12213, None
