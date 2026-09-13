import asyncio
import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.db.store import get_default_store

from .helpers import (
    SUPPORT_REQUISITION_ITEM_ID,
    SUPPORT_REQUISITION_RESULT_OK,
    SUPPORT_REQUISITION_RESULT_FAILED,
    SUPPORT_REQUISITION_RESULT_NOT_ENOUGH_MEDALS,
    SUPPORT_REQUISITION_RESULT_LIMIT_REACHED,
    load_support_requisition_config,
    get_random_requisition_ship_by_rarity,
    select_support_requisition_rarity,
    blank_assist_ship_info,
)
from src.answer.shipinfo.builder import build_ship_infos


def handle_request_player_assist_ship(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        data = protobuf.CS_12301()
        data.ParseFromString(buffer)
    except Exception as e:
        return 0, 12301, e

    _ = data.type
    response = protobuf.SC_12302()
    for _ in data.id_list:
        response.ship_list.append(blank_assist_ship_info())

    asyncio.create_task(client.send_message(12302, response))
    return 0, 12302, None


def handle_support_ship_requisition(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        data = protobuf.CS_16100()
        data.ParseFromString(buffer)
    except Exception as e:
        print("handle_support_ship_requisition")
        print(e)
        return 0, 16100, e

    response = protobuf.SC_16101()
    response.result = SUPPORT_REQUISITION_RESULT_FAILED

    count = data.cnt
    if count == 0 or count > 10:
        asyncio.create_task(client.send_message(16101, response))
        return 0, 16101, None

    config = load_support_requisition_config()
    if config is None:
        asyncio.create_task(client.send_message(16101, response))
        return 0, 16101, None

    now_unix = int(time.time())
    now = time.gmtime(now_unix)
    month_key = now.tm_year * 100 + now.tm_mon

    if client.commander.support_requisition_month != month_key:
        client.commander.support_requisition_month = month_key
        client.commander.support_requisition_count = 0

    if client.commander.support_requisition_count + count > config["monthly_cap"]:
        response.result = SUPPORT_REQUISITION_RESULT_LIMIT_REACHED
        asyncio.create_task(client.send_message(16101, response))
        return 0, 16101, None

    cost = config["cost"] * count
    from src.orm.item import has_enough_item, consume_item
    if not has_enough_item(client.commander.commander_id, SUPPORT_REQUISITION_ITEM_ID, cost):
        response.result = SUPPORT_REQUISITION_RESULT_NOT_ENOUGH_MEDALS
        asyncio.create_task(client.send_message(16101, response))
        return 0, 16101, None

    ship_templates = []
    for _ in range(count):
        try:
            rarity = select_support_requisition_rarity(config["rarity_weights"])
        except (ValueError, IndexError):
            print('handle_support_ship_requisition')
            print(ValueError)
            print(IndexError)
            asyncio.create_task(client.send_message(16101, response))
            return 0, 16101, None
        ship_template = get_random_requisition_ship_by_rarity(rarity)
        if ship_template is None:
            print('ship_template is None')
            asyncio.create_task(client.send_message(16101, response))
            return 0, 16101, None
        ship_templates.append(ship_template)

    consume_item(client.commander.commander_id, SUPPORT_REQUISITION_ITEM_ID, cost)

    # Ship creation lives in ONE place: commander.add_ship -> owned_ship.add_ship
    # (global id allocation, auto-lock, default equipment slots, in-memory
    # owned_ships_map cache update). The full SHIPINFO snapshot is then built
    # by shipinfo.builder (skills, equip slots, ...) — a minimal snapshot here
    # used to show the new ship without skills/equipment until re-login.
    ship_entries = []
    for template_id in ship_templates:
        try:
            new_ship = client.commander.add_ship(template_id)
        except Exception as e:
            print(e)
            return 0, 16101, e
        ship_entries.append(new_ship)

    store = get_default_store()
    store.execute(
        "UPDATE commanders SET support_requisition_count = support_requisition_count + $1, support_requisition_month = $3 WHERE commander_id = $2",
        count, client.commander.commander_id, month_key
    )
    if hasattr(client.commander, "support_requisition_count"):
        client.commander.support_requisition_count += count
    if hasattr(client.commander, "support_requisition_month"):
        client.commander.support_requisition_month = month_key

    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 192, 0, count)
        schedule_possession_sync(client)
    except Exception:
        pass

    response.result = SUPPORT_REQUISITION_RESULT_OK
    for s in build_ship_infos(ship_entries, client.commander.commander_id):
        response.ship_list.append(s)

    asyncio.create_task(client.send_message(16101, response))
    return 0, 16101, None
