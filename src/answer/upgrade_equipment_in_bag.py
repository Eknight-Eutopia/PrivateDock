import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

_EQUIP_RESPONSE_ID = 14005


from src.orm.owned_equipment import (
    load_equipment_config as _load_equipment_config,
    compute_equipment_upgrade_costs as _compute_equipment_upgrade_costs,
)


def _send_upgrade_bag_result(client, result: int):
    asyncio.create_task(client.send_message(_EQUIP_RESPONSE_ID, protobuf.SC_14005(result=result)))


def handle_upgrade_equipment_in_bag(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        _send_upgrade_bag_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    payload = protobuf.CS_14004()
    if not payload.ParseFromString(buffer):
        _send_upgrade_bag_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    equip_id = payload.equip_id
    lv = payload.lv
    if equip_id == 0 or lv == 0:
        _send_upgrade_bag_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    if (getattr(client.commander, "owned_equipment_map", None) is None
            or getattr(client.commander, "owned_resources_map", None) is None
            or getattr(client.commander, "commander_items_map", None) is None
            or getattr(client.commander, "misc_items_map", None) is None):
        try:
            client.commander.load()
        except Exception as e:
            _send_upgrade_bag_result(client, 1)
            return 0, _EQUIP_RESPONSE_ID, e

    owned_map = getattr(client.commander, "owned_equipment_map", {})
    owned = owned_map.get(equip_id)
    if owned is None or owned.get("count", 0) < 1:
        _send_upgrade_bag_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    upgraded_id, item_costs, coin_cost = _compute_equipment_upgrade_costs(equip_id, lv)
    if upgraded_id is None:
        _send_upgrade_bag_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    if coin_cost != 0 and not client.commander.has_enough_resource(1, coin_cost):
        _send_upgrade_bag_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    for item_id, count in item_costs.items():
        if not client.commander.has_enough_item(item_id, count):
            _send_upgrade_bag_result(client, 1)
            return 0, _EQUIP_RESPONSE_ID, None

    try:
        if coin_cost != 0:
            client.commander.consume_resource(1, coin_cost)
        for item_id, count in item_costs.items():
            if count == 0:
                continue
            client.commander.consume_item(item_id, count)

        from src.orm.owned_equipment import add_owned_equipment
        from src.orm.equipment import remove_owned_equipment
        remove_owned_equipment(client.commander.commander_id, equip_id, 1)
        add_owned_equipment(client.commander.commander_id, upgraded_id, 1)

        if equip_id in owned_map:
            owned_map[equip_id]["count"] -= 1
            if owned_map[equip_id]["count"] <= 0:
                del owned_map[equip_id]
        if upgraded_id in owned_map:
            owned_map[upgraded_id]["count"] = owned_map.get(upgraded_id, {}).get("count", 0) + 1
        else:
            owned_map[upgraded_id] = {"commander_id": client.commander.commander_id, "equipment_id": upgraded_id, "count": 1}
    except Exception as e:
        _send_upgrade_bag_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, e

    from src.answer import schedule_emit
    schedule_emit(client, 40, 0, 1)
    _send_upgrade_bag_result(client, 0)
    return 0, _EQUIP_RESPONSE_ID, None