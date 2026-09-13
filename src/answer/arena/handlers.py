import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

from .helpers import (
    load_config,
    refresh_if_needed,
    refresh_shop,
    build_shop_list,
    load_arena_buy_counts,
    has_enough_resource,
    consume_resource,
)


def handle_get_arena_shop(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_18100()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 18101, e

    import time
    now = int(time.time())

    config = load_config()
    if config is None:
        response = protobuf.SC_18101()
        asyncio.create_task(client.send_message(18101, response))
        return 0, 18101, None

    state = refresh_if_needed(client.commander.commander_id, now)

    buy_counts = load_arena_buy_counts(client.commander.commander_id)
    shop_list = build_shop_list(state["flash_count"], config, buy_counts)
    response = protobuf.SC_18101()
    response.flash_count = state["flash_count"]
    response.arena_shop_list.extend(shop_list)
    response.next_flash_time = state["next_flash_time"]

    asyncio.create_task(client.send_message(18101, response))
    return 0, 18101, None


def handle_refresh_arena_shop(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_18102()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 18103, e

    import time
    now = int(time.time())
    response = protobuf.SC_18103()
    response.result = 0

    config = load_config()
    if config is None:
        response.result = 1
        asyncio.create_task(client.send_message(18103, response))
        return 0, 18103, None

    state = refresh_if_needed(client.commander.commander_id, now)

    next_flash_count = state["flash_count"] + 1
    if next_flash_count > len(config.template.refresh_price):
        response.result = 1
        asyncio.create_task(client.send_message(18103, response))
        return 0, 18103, None

    refresh_cost = config.template.refresh_price[next_flash_count - 1]
    if refresh_cost > 0 and not has_enough_resource(client.commander.commander_id, 4, refresh_cost):
        response.result = 1
        asyncio.create_task(client.send_message(18103, response))
        return 0, 18103, None

    state, shop_list, cost = refresh_shop(client.commander.commander_id, now, config)
    if cost > 0:
        consume_resource(client.commander.commander_id, 4, cost)

    response.arena_shop_list.extend(shop_list)
    asyncio.create_task(client.send_message(18103, response))
    return 0, 18103, None
