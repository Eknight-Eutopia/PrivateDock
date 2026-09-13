import asyncio
import re
from typing import Optional

from src.connection.client import Client
from src.orm.commander import create_commander
from src.protobuf import protobuf
from src.config.config import current
from src.logger.logger import log_event, LOG_LEVEL_ERROR

from .helpers import (
    CREATE_PLAYER_NAME_MIN,
    CREATE_PLAYER_NAME_MAX,
    STARTER_SHIP_IDS,
)


def handle_create_new_player(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_10024()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 10025, e

    response = protobuf.SC_10025()
    response.result = 0
    response.user_id = 0

    nickname = payload.nick_name
    device_id = payload.device_id

    if not device_id:
        response.result = 1
        asyncio.create_task(client.send_message(10025, response))
        return 0, 10025, None

    name_length = len(nickname)
    if name_length < CREATE_PLAYER_NAME_MIN:
        response.result = 2012
        asyncio.create_task(client.send_message(10025, response))
        return 0, 10025, None

    if name_length > CREATE_PLAYER_NAME_MAX:
        response.result = 2011
        asyncio.create_task(client.send_message(10025, response))
        return 0, 10025, None

    create_config = current().create_player
    if create_config.name_blacklist:
        lower_name = nickname.lower()
        for blocked in create_config.name_blacklist:
            blocked = blocked.strip()
            if not blocked:
                continue
            if blocked.lower() in lower_name:
                response.result = 2013
                asyncio.create_task(client.send_message(10025, response))
                return 0, 10025, None

    if create_config.name_illegal_pattern:
        try:
            matcher = re.compile(create_config.name_illegal_pattern)
            if matcher.search(nickname):
                response.result = 2014
                asyncio.create_task(client.send_message(10025, response))
                return 0, 10025, None
        except re.error as e:
            return 0, 10025, e

    ship_id = payload.ship_id
    if ship_id not in STARTER_SHIP_IDS:
        response.result = 1
        asyncio.create_task(client.send_message(10025, response))
        return 0, 10025, None

    asyncio.create_task(_do_create_player(nickname, device_id, ship_id, client, response))
    return 0, 10025, None


async def _do_create_player(nickname, device_id, ship_id, client, response):
    from .helpers import get_device_auth_map, get_yostarus_map_by_arg2, check_commander_name_availability
    from .helpers import upsert_device_auth_map

    device_mapping = await get_device_auth_map(device_id)
    if device_mapping is not None:
        if device_mapping["account_id"] != 0:
            response.result = 1011
            await client.send_message(10025, response)
            return
        if client.auth_arg2 == 0:
            client.auth_arg2 = device_mapping["arg2"]

    if client.auth_arg2 == 0:
        response.result = 1
        await client.send_message(10025, response)
        return

    yostarus_mapping = await get_yostarus_map_by_arg2(client.auth_arg2)
    if yostarus_mapping is not None:
        response.result = 1011
        await client.send_message(10025, response)
        return

    name_check = await check_commander_name_availability(nickname)
    if name_check == "name_exists":
        response.result = 2015
        await client.send_message(10025, response)
        return

    try:
        account_id = await create_commander(client, client.auth_arg2, nickname, [ship_id])
    except Exception as e:
        log_event("Server", "SC_10025", f"failed to create commander: {e}", LOG_LEVEL_ERROR)
        response.result = 18
        await client.send_message(10025, response)
        return

    await upsert_device_auth_map(device_id, client.auth_arg2, account_id)

    from src.orm import get_commander_core_by_id
    from src.orm.active_commander import register_active_client
    try:
        client.commander = await get_commander_core_by_id(account_id)
        if client.commander is not None:
            client.commander.load()
            register_active_client(client.commander.commander_id, client)
    except Exception as e:
        log_event("Server", "SC_10025", f"failed to load newly created commander: {e}", LOG_LEVEL_ERROR)

    response.user_id = account_id
    await client.send_message(10025, response)
