import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

EQUIP_BAG_MAX = 4096
COMPOSE_EQUIPMENT_RESPONSE_ID = 14007


def handle_compose_equipment(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_14007(result=1)

    try:
        payload = protobuf.CS_14006()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, e

    compose_id = payload.id
    num = payload.num
    if compose_id == 0 or num == 0:
        asyncio.create_task(client.send_message(COMPOSE_EQUIPMENT_RESPONSE_ID, response))
        return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, None

    from src.db.store import NotFoundError
    from src.orm.game_data import get_compose_data_template_entry

    try:
        recipe = get_compose_data_template_entry(compose_id)
    except NotFoundError:
        asyncio.create_task(client.send_message(COMPOSE_EQUIPMENT_RESPONSE_ID, response))
        return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, None

    if recipe is None:
        asyncio.create_task(client.send_message(COMPOSE_EQUIPMENT_RESPONSE_ID, response))
        return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, None

    equip_id = recipe.get("equip_id", 0)
    material_id = recipe.get("material_id", 0)
    material_num = recipe.get("material_num", 0)
    gold_num = recipe.get("gold_num", 0)

    if equip_id == 0 or material_id == 0 or material_num == 0:
        asyncio.create_task(client.send_message(COMPOSE_EQUIPMENT_RESPONSE_ID, response))
        return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, None

    if getattr(client.commander, "owned_equipments_map", None) is None:
        try:
            client.commander.load()
        except Exception as e:
            return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, e

    if client.commander.equipment_bag_count() + num > EQUIP_BAG_MAX:
        asyncio.create_task(client.send_message(COMPOSE_EQUIPMENT_RESPONSE_ID, response))
        return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, None

    gold_cost = gold_num * num
    material_cost = material_num * num

    if gold_cost != 0 and not client.commander.has_enough_resource(1, gold_cost):
        asyncio.create_task(client.send_message(COMPOSE_EQUIPMENT_RESPONSE_ID, response))
        return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, None

    if not client.commander.has_enough_item(material_id, material_cost):
        asyncio.create_task(client.send_message(COMPOSE_EQUIPMENT_RESPONSE_ID, response))
        return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, None

    try:
        if gold_cost != 0:
            client.commander.consume_resource(1, gold_cost)
        if material_cost != 0:
            client.commander.consume_item(material_id, material_cost)
        from src.orm.owned_equipment import add_owned_equipment
        add_owned_equipment(client.commander.commander_id, equip_id, num)
    except Exception as e:
        asyncio.create_task(client.send_message(COMPOSE_EQUIPMENT_RESPONSE_ID, response))
        return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, e

    response.result = 0
    from src.answer import schedule_emit
    schedule_emit(client, 42, 0, num)
    asyncio.create_task(client.send_message(COMPOSE_EQUIPMENT_RESPONSE_ID, response))
    return 0, COMPOSE_EQUIPMENT_RESPONSE_ID, None
