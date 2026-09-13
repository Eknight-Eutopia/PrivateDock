import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.db.store import NotFoundError


def handle_get_rival_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 18105
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    requested_id = payload.get("id", 0)

    from src.orm.players import load_commander_with_details
    try:
        commander = load_commander_with_details(requested_id)
    except NotFoundError:
        response = {"info": _rival_info_sentinel()}
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None
    except Exception as e:
        return 0, packet_id, e

    info = _build_rival_target_info(commander)
    response = {"info": info}
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _rival_info_sentinel() -> dict:
    return {
        "id": 0,
        "level": 0,
        "name": "",
        "score": 0,
        "rank": 0,
        "vanguard_ship_list": None,
        "main_ship_list": None,
        "display": None,
    }


def _build_rival_target_info(commander) -> dict:
    if isinstance(commander, dict):
        icon = commander.get("display_icon_id", 0)
        skin = commander.get("display_skin_id", 0)
        icon_frame = commander.get("selected_icon_frame_id", 0)
        chat_frame = commander.get("selected_chat_frame_id", 0)
        icon_theme = commander.get("display_icon_theme_id", 0)
        commander_id = commander.get("commander_id", 0)
        level = commander.get("level", 0)
        name = commander.get("name", "")
        secretaries = commander.get("secretaries", [])
        ships = commander.get("ships", [])
        fleets = commander.get("fleets", [])
    else:
        icon = getattr(commander, "display_icon_id", 0)
        skin = getattr(commander, "display_skin_id", 0)
        icon_frame = getattr(commander, "selected_icon_frame_id", 0)
        chat_frame = getattr(commander, "selected_chat_frame_id", 0)
        icon_theme = getattr(commander, "display_icon_theme_id", 0)
        commander_id = getattr(commander, "commander_id", 0)
        level = getattr(commander, "level", 0)
        name = getattr(commander, "name", "")
        secretaries = commander.get_secretaries() if hasattr(commander, "get_secretaries") else []
        ships = getattr(commander, "ships", [])
        fleets = getattr(commander, "fleets", [])

    display = {
        "icon": icon,
        "skin": skin,
        "icon_frame": icon_frame,
        "chat_frame": chat_frame,
        "icon_theme": icon_theme,
        "marry_flag": 0,
        "transform_flag": 0,
    }

    if display["icon"] == 0 and len(secretaries) > 0:
        sec = secretaries[0]
        display["icon"] = sec.get("ship_id", 0) if isinstance(sec, dict) else getattr(sec, "ship_id", 0)
    if display["skin"] == 0 and len(secretaries) > 0:
        sec = secretaries[0]
        display["skin"] = sec.get("skin_id", 0) if isinstance(sec, dict) else getattr(sec, "skin_id", 0)

    vanguard_ships, main_ships = _build_rival_defense_ship_lists(ships, fleets)

    return {
        "id": commander_id,
        "level": level,
        "name": name,
        "score": 0,
        "rank": 0,
        "vanguard_ship_list": vanguard_ships,
        "main_ship_list": main_ships,
        "display": display,
    }


def _build_rival_defense_ship_lists(ships: list, fleets: list) -> tuple:
    ships_by_id = {}
    for ship in ships:
        if isinstance(ship, dict):
            ships_by_id[ship.get("id", 0)] = ship
        else:
            ships_by_id[getattr(ship, "id", 0)] = ship

    fleet_ids = _commander_fleet_ship_ids(fleets)
    preferred_ids = fleet_ids
    if not preferred_ids:
        preferred_ids = _stable_owned_ship_ids(ships)

    candidates = []
    for sid in preferred_ids:
        ship = ships_by_id.get(sid)
        if ship is None:
            continue
        candidates.append(ship)
        if len(candidates) >= 6:
            break

    if not candidates and fleet_ids:
        for sid in _stable_owned_ship_ids(ships):
            ship = ships_by_id.get(sid)
            if ship is None:
                continue
            candidates.append(ship)
            if len(candidates) >= 6:
                break

    vanguard = []
    main = []
    used = set()

    for ship in candidates:
        if isinstance(ship, dict):
            ship_id = ship.get("id", 0)
            ship_type = ship.get("ship", {}).get("type", 0) if isinstance(ship.get("ship"), dict) else 0
        else:
            ship_id = getattr(ship, "id", 0)
            ship_type = getattr(getattr(ship, "ship", None), "type", 0)

        if len(vanguard) < 3 and _is_vanguard_ship_type(ship_type):
            vanguard.append(_to_proto_owned_ship(ship))
            used.add(ship_id)
            continue
        if len(main) < 3:
            main.append(_to_proto_owned_ship(ship))
            used.add(ship_id)

    for ship in candidates:
        if isinstance(ship, dict):
            ship_id = ship.get("id", 0)
        else:
            ship_id = getattr(ship, "id", 0)
        if ship_id in used:
            continue
        if len(vanguard) < 3:
            vanguard.append(_to_proto_owned_ship(ship))
            used.add(ship_id)
            continue
        if len(main) < 3:
            main.append(_to_proto_owned_ship(ship))
            used.add(ship_id)
        if len(vanguard) >= 3 and len(main) >= 3:
            break

    return vanguard, main


def _commander_fleet_ship_ids(fleets: list) -> list:
    for fleet in fleets:
        if isinstance(fleet, dict):
            game_id = fleet.get("game_id", 0)
            ship_list = fleet.get("ship_list", [])
        else:
            game_id = getattr(fleet, "game_id", 0)
            ship_list = getattr(fleet, "ship_list", [])
        if game_id != 1:
            continue
        return [int(s) for s in ship_list]
    return []


def _stable_owned_ship_ids(ships: list) -> list:
    result = []
    for ship in ships:
        if isinstance(ship, dict):
            result.append((ship.get("id", 0), ship.get("id", 0)))
        else:
            result.append((getattr(ship, "id", 0), getattr(ship, "id", 0)))
    result.sort(key=lambda x: x[0])
    return [sid for sid, _ in result]


def _is_vanguard_ship_type(ship_type: int) -> bool:
    return ship_type in (1, 2, 3, 18, 19, 8, 17)


def _to_proto_owned_ship(ship) -> dict:
    if isinstance(ship, dict):
        return {
            "id": ship.get("id", 0),
            "template_id": ship.get("template_id", 0),
            "level": ship.get("level", 0),
            "exp": ship.get("exp", 0),
            "pre_exp": ship.get("pre_exp", 0),
            "energy": ship.get("energy", 0),
            "is_locked": ship.get("is_locked", 0),
            "create_time": ship.get("create_time", 0),
            "ship": ship.get("ship", {}),
        }
    return {
        "id": getattr(ship, "id", 0),
        "template_id": getattr(ship, "template_id", 0),
        "level": getattr(ship, "level", 0),
        "exp": getattr(ship, "exp", 0),
        "pre_exp": getattr(ship, "pre_exp", 0),
        "energy": getattr(ship, "energy", 0),
        "is_locked": getattr(ship, "is_locked", 0),
        "create_time": getattr(ship, "create_time", 0),
        "ship": getattr(ship, "ship", {}),
    }
