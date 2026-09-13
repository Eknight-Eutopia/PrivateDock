import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def _make_14206(result=1, attr_temp_1=0, attr_temp_2=0):
    return protobuf.SC_14206(result=result, attr_temp_1=attr_temp_1, attr_temp_2=attr_temp_2)


def handle_reforge_sp_weapon(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 14206
    payload = protobuf.CS_14205()
    try:
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, packet_id, e

    if client.commander is None:
        asyncio.create_task(client.send_message(packet_id, _make_14206()))
        return 0, packet_id, None

    if (getattr(client.commander, "owned_sp_weapons_map", None) is None
            or getattr(client.commander, "owned_ships_map", None) is None):
        try:
            client.commander.load()
        except Exception as e:
            return 0, packet_id, e

    spweapons_map = getattr(client.commander, "owned_sp_weapons_map", None) or {}
    spweapon_id = payload.spweapon_id
    spweapon = spweapons_map.get(spweapon_id)
    if spweapon is None:
        asyncio.create_task(client.send_message(packet_id, _make_14206()))
        return 0, packet_id, None

    ship_id = payload.ship_id
    if ship_id != 0:
        ships_map = getattr(client.commander, "ships_map", None) or getattr(client.commander, "owned_ships_map", None) or {}
        if ship_id not in ships_map:
            asyncio.create_task(client.send_message(packet_id, _make_14206()))
            return 0, packet_id, None
        equipped_ship_id = spweapon.get("equipped_ship_id", 0) if isinstance(spweapon, dict) else getattr(spweapon, "equipped_ship_id", 0)
        if equipped_ship_id != 0 and equipped_ship_id != ship_id:
            asyncio.create_task(client.send_message(packet_id, _make_14206()))
            return 0, packet_id, None

    attr_temp_1 = spweapon.get("attr_temp_1", 0) if isinstance(spweapon, dict) else getattr(spweapon, "attr_temp_1", 0)
    attr_temp_2 = spweapon.get("attr_temp_2", 0) if isinstance(spweapon, dict) else getattr(spweapon, "attr_temp_2", 0)
    template_id = spweapon.get("template_id", 0) if isinstance(spweapon, dict) else getattr(spweapon, "template_id", 0)

    if attr_temp_1 != 0 or attr_temp_2 != 0:
        asyncio.create_task(client.send_message(packet_id, _make_14206()))
        return 0, packet_id, None

    from src.orm.game_data import get_sp_weapon_data_statistics_config, get_sp_weapon_upgrade_config

    spweapon_config = get_sp_weapon_data_statistics_config(template_id)
    if not spweapon_config:
        asyncio.create_task(client.send_message(packet_id, _make_14206()))
        return 0, packet_id, None

    upgrade_id = spweapon_config.get("upgrade_id", 0) if isinstance(spweapon_config, dict) else getattr(spweapon_config, "upgrade_id", 0)
    value1_random = spweapon_config.get("value_1_random", spweapon_config.get("value1_random", 0)) if isinstance(spweapon_config, dict) else getattr(spweapon_config, "value_1_random", getattr(spweapon_config, "value1_random", 0))
    value2_random = spweapon_config.get("value_2_random", spweapon_config.get("value2_random", 0)) if isinstance(spweapon_config, dict) else getattr(spweapon_config, "value_2_random", getattr(spweapon_config, "value2_random", 0))

    upgrade_config = get_sp_weapon_upgrade_config(upgrade_id)
    if not upgrade_config:
        asyncio.create_task(client.send_message(packet_id, _make_14206()))
        return 0, packet_id, None

    reset_use_item = upgrade_config.get("reset_use_item", []) if isinstance(upgrade_config, dict) else getattr(upgrade_config, "reset_use_item", [])

    cost_items = []
    for cost in reset_use_item:
        if isinstance(cost, dict):
            cost_item_id = cost.get("item_id", 0)
            cost_count = cost.get("count", 0)
        elif isinstance(cost, (list, tuple)) and len(cost) >= 2:
            cost_item_id = cost[0]
            cost_count = cost[1]
        else:
            cost_item_id = getattr(cost, "item_id", 0)
            cost_count = getattr(cost, "count", 0)
        if cost_item_id > 0 and cost_count > 0:
            if not client.commander.has_enough_item(cost_item_id, cost_count):
                asyncio.create_task(client.send_message(packet_id, _make_14206()))
                return 0, packet_id, None
            cost_items.append((cost_item_id, cost_count))

    attr_temp_1_rolled = _roll_sp_weapon_temp_attr(value1_random)
    attr_temp_2_rolled = _roll_sp_weapon_temp_attr(value2_random)

    from src.orm.spweapon import save_owned_sp_weapon
    try:
        for cost_item_id, cost_count in cost_items:
            client.commander.consume_item(cost_item_id, cost_count)

        if isinstance(spweapon, dict):
            spweapon["attr_temp_1"] = attr_temp_1_rolled
            spweapon["attr_temp_2"] = attr_temp_2_rolled
        else:
            spweapon.attr_temp_1 = attr_temp_1_rolled
            spweapon.attr_temp_2 = attr_temp_2_rolled
        save_owned_sp_weapon(spweapon)
    except Exception as e:
        return 0, packet_id, e

    asyncio.create_task(client.send_message(packet_id, _make_14206(0, attr_temp_1_rolled, attr_temp_2_rolled)))
    return 0, packet_id, None


def _roll_sp_weapon_temp_attr(max_val: int) -> int:
    import random
    if max_val == 0:
        return 0
    return random.randint(0, max_val)

