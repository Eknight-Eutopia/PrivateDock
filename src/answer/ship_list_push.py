import asyncio
from typing import Optional

from src.connection.client import Client


def _ship_to_dict(ship) -> dict:
    id_ = getattr(ship, "id", None) or (ship.get("id", 0) if isinstance(ship, dict) else 0)
    template_id = getattr(ship, "ship_id", None) or (ship.get("ship_id", 0) if isinstance(ship, dict) else 0)
    level = getattr(ship, "level", None) or (ship.get("level", 0) if isinstance(ship, dict) else 0)
    exp = getattr(ship, "exp", None) or (ship.get("exp", 0) if isinstance(ship, dict) else 0)
    energy = getattr(ship, "energy", None) or (ship.get("energy", 0) if isinstance(ship, dict) else 0)
    intimacy = getattr(ship, "intimacy", None) or (ship.get("intimacy", 0) if isinstance(ship, dict) else 0)
    max_level = getattr(ship, "max_level", None) or (ship.get("max_level", 0) if isinstance(ship, dict) else 0)
    skin_id = getattr(ship, "skin_id", None) or (ship.get("skin_id", 0) if isinstance(ship, dict) else 0)
    activity_npc = getattr(ship, "activity_npc", None) or (ship.get("activity_npc", 0) if isinstance(ship, dict) else 0)
    custom_name = getattr(ship, "custom_name", None) or (ship.get("custom_name", "") if isinstance(ship, dict) else "")
    is_locked = getattr(ship, "is_locked", None) or (ship.get("is_locked", False) if isinstance(ship, dict) else False)
    propose = getattr(ship, "propose", None) or (ship.get("propose", False) if isinstance(ship, dict) else False)
    proficiency = getattr(ship, "proficiency", None) or (ship.get("proficiency", False) if isinstance(ship, dict) else False)
    common_flag = getattr(ship, "common_flag", None) or (ship.get("common_flag", False) if isinstance(ship, dict) else False)

    if isinstance(ship, dict):
        state = ship.get("state", 0)
        state_info_1 = ship.get("state_info1", 0)
        state_info_2 = ship.get("state_info2", 0)
        state_info_3 = ship.get("state_info3", 0)
        state_info_4 = ship.get("state_info4", 0)
    else:
        state = getattr(ship, "state", 0)
        state_info_1 = getattr(ship, "state_info1", 0)
        state_info_2 = getattr(ship, "state_info2", 0)
        state_info_3 = getattr(ship, "state_info3", 0)
        state_info_4 = getattr(ship, "state_info4", 0)

    return {
        "id": id_,
        "template_id": template_id,
        "level": level,
        "exp": exp,
        "energy": energy,
        "intimacy": intimacy,
        "is_locked": 1 if is_locked else 0,
        "max_level": max_level,
        "propose": 1 if propose else 0,
        "proficiency": 1 if proficiency else 0,
        "skin_id": skin_id,
        "common_flag": 1 if common_flag else 0,
        "activity_npc": activity_npc,
        "name": custom_name,
        "create_time": 0,
        "change_name_timestamp": 0,
        "state": {
            "state": state,
            "state_info_1": state_info_1,
            "state_info_2": state_info_2,
            "state_info_3": state_info_3,
            "state_info_4": state_info_4,
        },
    }


def push_new_ships(client: Client, ships: list) -> tuple[int, int, Optional[Exception]]:
    if not ships:
        return 0, 0, None
    owned_ships = [s for s in ships if s is not None]
    if not owned_ships:
        return 0, 0, None
    ship_list = [_ship_to_dict(s) for s in owned_ships]
    asyncio.create_task(client.send_message(12042, {"ship_list": ship_list}))
    return 0, 12042, None
