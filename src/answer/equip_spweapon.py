import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_equip_sp_weapon(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 14202
    payload = protobuf.CS_14201()
    try:
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, packet_id, e

    if client.commander is None:
        asyncio.create_task(client.send_message(packet_id, protobuf.SC_14202(result=1)))
        return 0, packet_id, None

    if (getattr(client.commander, "owned_sp_weapons_map", None) is None
            or getattr(client.commander, "owned_ships_map", None) is None):
        try:
            client.commander.load()
        except Exception as e:
            return 0, packet_id, e

    spweapons_map = getattr(client.commander, "owned_sp_weapons_map", None) or {}
    ships_map = getattr(client.commander, "ships_map", None) or getattr(client.commander, "owned_ships_map", None) or {}

    spweapon_id = payload.spweapon_id
    ship_id = payload.ship_id
    owner_id = client.commander.commander_id

    from src.orm.spweapon import update_sp_weapon_equip, update_sp_weapon_unequip_others, update_sp_weapon_unequip_ship

    if ship_id != 0 and ship_id not in ships_map:
        asyncio.create_task(client.send_message(packet_id, protobuf.SC_14202(result=1)))
        return 0, packet_id, None

    # Case 1: unequip from ship (spweapon_id == 0)
    if spweapon_id == 0:
        if ship_id == 0:
            asyncio.create_task(client.send_message(packet_id, protobuf.SC_14202(result=1)))
            return 0, packet_id, None

        try:
            update_sp_weapon_unequip_ship(owner_id, ship_id)
        except Exception as e:
            return 0, packet_id, e

        owned_sp = getattr(client.commander, "owned_sp_weapons", []) or []
        for entry in owned_sp:
            eeq = entry.get("equipped_ship_id", 0) if isinstance(entry, dict) else getattr(entry, "equipped_ship_id", 0)
            if eeq == ship_id:
                if isinstance(entry, dict):
                    entry["equipped_ship_id"] = 0
                else:
                    entry.equipped_ship_id = 0
        for sp in spweapons_map.values():
            eeq = sp.get("equipped_ship_id", 0) if isinstance(sp, dict) else getattr(sp, "equipped_ship_id", 0)
            if eeq == ship_id:
                if isinstance(sp, dict):
                    sp["equipped_ship_id"] = 0
                else:
                    sp.equipped_ship_id = 0

        asyncio.create_task(client.send_message(packet_id, protobuf.SC_14202(result=0)))
        return 0, packet_id, None

    # Case 2: equip / change weapon (spweapon_id != 0)
    if spweapon_id not in spweapons_map:
        asyncio.create_task(client.send_message(packet_id, protobuf.SC_14202(result=1)))
        return 0, packet_id, None

    try:
        if ship_id != 0:
            update_sp_weapon_unequip_others(owner_id, ship_id, spweapon_id)
        update_sp_weapon_equip(owner_id, spweapon_id, ship_id)
    except Exception as e:
        return 0, packet_id, e

    if ship_id != 0:
        owned_sp = getattr(client.commander, "owned_sp_weapons", []) or []
        for entry in owned_sp:
            eid = entry.get("id", 0) if isinstance(entry, dict) else getattr(entry, "id", 0)
            eeq = entry.get("equipped_ship_id", 0) if isinstance(entry, dict) else getattr(entry, "equipped_ship_id", 0)
            if eid != spweapon_id and eeq == ship_id:
                if isinstance(entry, dict):
                    entry["equipped_ship_id"] = 0
                else:
                    entry.equipped_ship_id = 0
        for sp in spweapons_map.values():
            eid = sp.get("id", 0) if isinstance(sp, dict) else getattr(sp, "id", 0)
            eeq = sp.get("equipped_ship_id", 0) if isinstance(sp, dict) else getattr(sp, "equipped_ship_id", 0)
            if eid != spweapon_id and eeq == ship_id:
                if isinstance(sp, dict):
                    sp["equipped_ship_id"] = 0
                else:
                    sp.equipped_ship_id = 0

    sp = spweapons_map.get(spweapon_id)
    if sp is not None:
        if isinstance(sp, dict):
            sp["equipped_ship_id"] = ship_id
        else:
            sp.equipped_ship_id = ship_id

    for entry in getattr(client.commander, "owned_sp_weapons", []) or []:
        eid = entry.get("id", 0) if isinstance(entry, dict) else getattr(entry, "id", 0)
        if eid == spweapon_id:
            if isinstance(entry, dict):
                entry["equipped_ship_id"] = ship_id
            else:
                entry.equipped_ship_id = ship_id

    if ship_id != 0:
        try:
            from src.answer.task_handlers import schedule_emit, schedule_possession_sync
            schedule_emit(client, 1060, 0, 1)
            schedule_possession_sync(client)
        except Exception:
            pass

    asyncio.create_task(client.send_message(packet_id, protobuf.SC_14202(result=0)))
    return 0, packet_id, None

