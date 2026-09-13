import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .helpers import (
    update_commander_random_flag_ship_enabled,
    update_commander_random_ship_mode,
    apply_random_flag_ship_updates,
)


def handle_toggle_random_flag_ship(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12204()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12205, e

    response = protobuf.SC_12205()
    response.result = 0
    flag = payload.flag

    if flag > 1:
        response.result = 1
        asyncio.create_task(client.send_message(12205, response))
        return 0, 12205, None

    enabled = flag == 1
    try:
        update_commander_random_flag_ship_enabled(client.commander.commander_id, enabled)
    except Exception:
        response.result = 1
        asyncio.create_task(client.send_message(12205, response))
        return 0, 12205, None

    client.commander.random_flag_ship_enabled = enabled
    asyncio.create_task(client.send_message(12205, response))
    return 0, 12205, None


def handle_change_random_flag_ship_mode(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12206()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12207, e

    response = protobuf.SC_12207()
    response.result = 0
    mode = payload.flag

    if mode < 1 or mode > 3:
        response.result = 1
        asyncio.create_task(client.send_message(12207, response))
        return 0, 12207, None

    try:
        update_commander_random_ship_mode(client.commander.commander_id, mode)
    except Exception:
        response.result = 1
        asyncio.create_task(client.send_message(12207, response))
        return 0, 12207, None

    client.commander.random_ship_mode = mode
    asyncio.create_task(client.send_message(12207, response))
    return 0, 12207, None


def handle_change_random_flag_ships(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        data = protobuf.CS_12208()
        data.ParseFromString(buffer)
    except Exception as e:
        return 0, 12209, e

    response = protobuf.SC_12209()
    response.result = 0

    updates = []
    for entry in data.ship_shadow_list:
        if entry is None:
            response.result = 1
            asyncio.create_task(client.send_message(12209, response))
            return 0, 12209, None

        ship_id = entry.key
        if ship_id not in client.commander.owned_ships_map:
            response.result = 1
            asyncio.create_task(client.send_message(12209, response))
            return 0, 12209, None

        flag = entry.value2
        if flag > 1:
            response.result = 1
            asyncio.create_task(client.send_message(12209, response))
            return 0, 12209, None

        updates.append({
            "ship_id": ship_id,
            "phantom_id": entry.value1,
            "flag": flag,
        })

    if updates:
        try:
            apply_random_flag_ship_updates(client.commander.commander_id, updates)
        except Exception:
            response.result = 1
            asyncio.create_task(client.send_message(12209, response))
            return 0, 12209, None

    asyncio.create_task(client.send_message(12209, response))
    return 0, 12209, None
