import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.orm.item import add_item
from src.orm.resource import consume_resource
from .lesson_resource_packet_helpers import (
    CLASS_FIELD_RESOURCE_ID,
    load_class_resource_item_id,
    load_item_statistics_config,
    parse_usage_arg_exp_value,
)

PACKET_ID = 22010


def handle_harvest_class_resource(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    commander = client.commander
    if commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_22010(result=1, exp_in_well=0)))
        return 0, PACKET_ID, None

    if not hasattr(commander, "get_resource_count") or not hasattr(commander, "get_item_count"):
        try:
            commander.load()
        except Exception:
            pass

    exp_in_well = commander.get_resource_count(CLASS_FIELD_RESOURCE_ID)

    payload = protobuf.CS_22009()
    try:
        payload.ParseFromString(buffer)
    except Exception:
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_22010(result=1, exp_in_well=exp_in_well)))
        return 0, PACKET_ID, None

    response = protobuf.SC_22010(result=1, exp_in_well=exp_in_well)

    if payload.type != 0:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    class_item_id = load_class_resource_item_id()
    if class_item_id == 0:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    item_config = load_item_statistics_config(class_item_id)
    if item_config is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    pack_exp_value = parse_usage_arg_exp_value(item_config.get("usage_arg"))
    if pack_exp_value == 0 or item_config.get("max_num", 0) == 0:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    generated = exp_in_well // pack_exp_value
    current_count = commander.get_item_count(class_item_id)
    free_capacity = 0
    max_num = item_config["max_num"]
    if current_count < max_num:
        free_capacity = max_num - current_count

    claim_count = generated
    if claim_count > free_capacity:
        claim_count = free_capacity

    if claim_count == 0:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    consumed_exp = claim_count * pack_exp_value
    new_exp_in_well = exp_in_well - consumed_exp

    add_item(commander.commander_id, class_item_id, claim_count)
    consume_resource(commander.commander_id, CLASS_FIELD_RESOURCE_ID, consumed_exp)

    response = protobuf.SC_22010(result=0, exp_in_well=new_exp_in_well)
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
