import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_confirm_reforge_sp_weapon(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 14208
    payload = protobuf.CS_14207()
    payload.ParseFromString(buffer)

    response = protobuf.SC_14208(result=1)

    if client.commander is None:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    spweapons_map = getattr(client.commander, "owned_sp_weapons_map", None) or {}
    spweapon_id = payload.spweapon_id
    spweapon = spweapons_map.get(spweapon_id)
    if spweapon is None:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    ship_id = payload.ship_id
    if ship_id != 0:
        ships_map = getattr(client.commander, "ships_map", None) or getattr(client.commander, "owned_ships_map", None) or {}
        if ship_id not in ships_map:
            asyncio.create_task(client.send_message(packet_id, response))
            return 0, packet_id, None

        if isinstance(spweapon, dict):
            equipped_ship_id = spweapon.get("equipped_ship_id", 0)
        else:
            equipped_ship_id = getattr(spweapon, "equipped_ship_id", 0)
        if equipped_ship_id != 0 and equipped_ship_id != ship_id:
            asyncio.create_task(client.send_message(packet_id, response))
            return 0, packet_id, None

    cmd = payload.cmd
    if cmd == 0:
        pass
    elif cmd == 1:
        if isinstance(spweapon, dict):
            spweapon["attr_1"] = spweapon.get("attr_temp_1", 0)
            spweapon["attr_2"] = spweapon.get("attr_temp_2", 0)
        else:
            spweapon.attr_1 = getattr(spweapon, "attr_temp_1", 0)
            spweapon.attr_2 = getattr(spweapon, "attr_temp_2", 0)
    else:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    if isinstance(spweapon, dict):
        spweapon["attr_temp_1"] = 0
        spweapon["attr_temp_2"] = 0
    else:
        spweapon.attr_temp_1 = 0
        spweapon.attr_temp_2 = 0

    from src.orm.spweapon import save_owned_sp_weapon
    try:
        save_owned_sp_weapon(spweapon)
    except Exception as e:
        return 0, packet_id, e

    response.result = 0
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
