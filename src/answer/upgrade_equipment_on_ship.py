import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

_EQUIP_RESPONSE_ID = 14003


from src.orm.owned_equipment import (
    load_equipment_config as _load_equipment_config,
    compute_equipment_upgrade_costs as _compute_equipment_upgrade_costs,
    build_ship_equipment_from_memory as _build_ship_equipment_from_memory,
    apply_ship_equipment_update as _apply_ship_equipment_update,
)


def _send_upgrade_ship_result(client, result: int):
    asyncio.create_task(client.send_message(_EQUIP_RESPONSE_ID, protobuf.SC_14003(result=result)))


def handle_upgrade_equipment_on_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        _send_upgrade_ship_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    payload = protobuf.CS_14002()
    if not payload.ParseFromString(buffer):
        _send_upgrade_ship_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    ship_id = payload.ship_id
    pos = payload.pos
    lv = payload.lv
    if ship_id == 0 or pos == 0 or lv == 0:
        _send_upgrade_ship_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    if (getattr(client.commander, "owned_ships_map", None) is None
            or getattr(client.commander, "owned_resources_map", None) is None
            or getattr(client.commander, "commander_items_map", None) is None
            or getattr(client.commander, "misc_items_map", None) is None):
        try:
            client.commander.load()
        except Exception as e:
            _send_upgrade_ship_result(client, 1)
            return 0, _EQUIP_RESPONSE_ID, e

    ship = client.commander.owned_ships_map.get(ship_id)
    if ship is None:
        _send_upgrade_ship_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    from src.db.store import NotFoundError
    from src.orm.equipment import get_owned_ship_equipment
    try:
        current = get_owned_ship_equipment(ship.get("id", 0), pos)
        if current is not None:
            current = {
                "owner_id": current.get("owner_id", client.commander.commander_id),
                "ship_id": current.get("ship_id", ship.get("id", 0)),
                "pos": current.get("pos", pos),
                "equip_id": current.get("equip_id", 0),
                "skin_id": current.get("skin_id", 0),
            }
        else:
            current = _build_ship_equipment_from_memory(client.commander.commander_id, ship, pos)
    except NotFoundError:
        current = _build_ship_equipment_from_memory(client.commander.commander_id, ship, pos)
    except Exception as e:
        return 0, 14002, e

    if current.get("equip_id", 0) == 0:
        _send_upgrade_ship_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    upgraded_id, item_costs, coin_cost = _compute_equipment_upgrade_costs(current["equip_id"], lv)
    if upgraded_id is None:
        _send_upgrade_ship_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    if coin_cost != 0 and not client.commander.has_enough_resource(1, coin_cost):
        _send_upgrade_ship_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    for item_id, count in item_costs.items():
        if not client.commander.has_enough_item(item_id, count):
            _send_upgrade_ship_result(client, 1)
            return 0, _EQUIP_RESPONSE_ID, None

    try:
        if coin_cost != 0:
            client.commander.consume_resource(1, coin_cost)
        for item_id, count in item_costs.items():
            if count == 0:
                continue
            client.commander.consume_item(item_id, count)

        from src.orm.owned_equipment import upsert_owned_ship_equipment
        current["equip_id"] = upgraded_id
        upsert_owned_ship_equipment(current["owner_id"], current["ship_id"], current["pos"], current["equip_id"], current["skin_id"])
    except Exception as e:
        _send_upgrade_ship_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, e

    _apply_ship_equipment_update(ship, current)
    from src.answer import schedule_emit
    schedule_emit(client, 40, 0, 1)
    _send_upgrade_ship_result(client, 0)
    return 0, _EQUIP_RESPONSE_ID, None