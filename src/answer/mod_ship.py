import asyncio
import math
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


SHIP_MOD_STRENGTH_IDS = [2, 3, 4, 5, 6]


def _ship_mod_attr_exp(config) -> dict[int, int]:
    if len(config.get("attr_exp", [])) < len(SHIP_MOD_STRENGTH_IDS):
        raise Exception("ship strengthen attr_exp is incomplete")
    attr_exp = {}
    for strength_id in SHIP_MOD_STRENGTH_IDS:
        index = strength_id - 2
        attr_exp[strength_id] = config["attr_exp"][index]
    return attr_exp


def _ship_mod_additions(target_group: int, materials: list) -> dict[int, int]:
    from src.orm.owned_equipment import get_ship_template_config
    from src.orm.game_data import get_ship_strengthen_config

    additions = {sid: 0 for sid in SHIP_MOD_STRENGTH_IDS}
    for material in materials:
        template = get_ship_template_config(material["ship_id"])
        strengthen = get_ship_strengthen_config(template["strengthen_id"])
        attr_exp = _ship_mod_attr_exp(strengthen)
        for strength_id in SHIP_MOD_STRENGTH_IDS:
            addition = attr_exp.get(strength_id, 0)
            if template["group_type"] == target_group:
                addition *= 2
            additions[strength_id] = additions.get(strength_id, 0) + addition
    return additions


def _ship_mod_top_limit(level: int, durability: int) -> int:
    if durability == 0:
        return 0
    level_value = float(level)
    if level_value > 100:
        level_value = 100
    factor = 3 + 7 * level_value / 100
    value = factor * float(durability) * 0.1
    return int(math.floor(value))


def _ship_mod_strength_updates(ship: dict, config: dict, additions: dict[int, int]) -> dict[int, int]:
    durability = config.get("durability", [])
    level_exp = config.get("level_exp", [])
    if len(durability) < len(SHIP_MOD_STRENGTH_IDS) or len(level_exp) < len(SHIP_MOD_STRENGTH_IDS):
        raise Exception("ship strengthen config is incomplete")
    strengths = ship.get("strengths", [])
    current = {entry["strength_id"]: entry["exp"] for entry in strengths}
    updates = {}
    for strength_id in SHIP_MOD_STRENGTH_IDS:
        addition = additions.get(strength_id, 0)
        if addition == 0:
            continue
        index = strength_id - 2
        exp_ratio = level_exp[index]
        if exp_ratio == 0:
            exp_ratio = 1
        top_limit = _ship_mod_top_limit(ship["level"], durability[index])
        if top_limit == 0:
            continue
        cap = top_limit * exp_ratio
        new_exp = current.get(strength_id, 0) + addition
        if new_exp > cap:
            new_exp = cap
        updates[strength_id] = new_exp
    return updates
def _hydrate_owned_ships(commander, owned_ids: list[int]) -> None:
    """Load ships missing from the session cache straight from the DB (they can
    be mid-session grants - battle drops etc. - that never hit owned_ships_map)."""
    if not owned_ids:
        return
    owned_map = getattr(commander, "owned_ships_map", None)
    if owned_map is None:
        return
    missing = [oid for oid in owned_ids if oid not in owned_map]
    if not missing:
        return
    from src.orm.owned_ship import list_ships_by_ids
    for row in list_ships_by_ids(commander.commander_id, missing):
        owned_map[row[0]] = {
            "id": row[0],
            "owner_id": commander.commander_id,
            "ship_id": row[1],
            "level": row[2],
            "energy": row[4],
            "state": row[15],
            "state_info1": row[16],
            "intimacy": row[5],
            "exp": row[3],
            "surplus_exp": 0,
            "max_level": row[7],
            "is_locked": row[8],
            "propose": row[9],
            "create_time": row[12],
        }


def _collect_material_ships(commander, ship_id: int, material_ids: list[int]) -> Optional[list]:
    materials = []
    owned_map = commander.owned_ships_map if hasattr(commander, "owned_ships_map") else {}
    _hydrate_owned_ships(commander, material_ids)
    for material_id in material_ids:
        if material_id == ship_id:
            return None
        material = owned_map.get(material_id)
        if material is None:
            return None
        materials.append(material)
    return materials


def _apply_strength_updates(ship: dict, updates: dict[int, int]):
    if not updates:
        return
    strengths = ship.get("strengths", [])
    remaining = dict(updates)
    for entry in strengths:
        sid = entry["strength_id"]
        if sid in remaining:
            entry["exp"] = remaining.pop(sid)
            if not remaining:
                return
    for strength_id, exp in remaining.items():
        strengths.append({
            "owner_id": ship.get("owner_id", 0),
            "ship_id": ship.get("id", 0),
            "strength_id": strength_id,
            "exp": exp,
        })


def _send_mod_result(client, result: int):
    asyncio.create_task(client.send_message(12018, protobuf.SC_12018(result=result)))


def handle_mod_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12017()
    payload.ParseFromString(buffer)

    ship_id = payload.ship_id
    owned_map = getattr(client.commander, "owned_ships_map", {})
    ship = owned_map.get(ship_id)
    if ship is None:
        _hydrate_owned_ships(client.commander, [ship_id])
        ship = owned_map.get(ship_id)
    if ship is None:
        _send_mod_result(client, 1)
        return 0, 12018, None

    material_ids = list(payload.material_id_list)
    if not material_ids:
        _send_mod_result(client, 1)
        return 0, 12018, None

    materials = _collect_material_ships(client.commander, ship["id"], material_ids)
    if materials is None:
        _send_mod_result(client, 1)
        return 0, 12018, None

    try:
        from src.orm.game_data import get_ship_template_config, get_ship_strengthen_config
        from src.orm.owned_ship_strength import list_owned_ship_strengths, upsert_owned_ship_strength
        from src.orm.owned_ship import consume_mod_material_ships

        strengths = list_owned_ship_strengths(client.commander.commander_id, ship["id"])
        ship["strengths"] = [
            {
                "owner_id": s.owner_id,
                "ship_id": s.ship_id,
                "strength_id": s.strength_id,
                "exp": s.exp,
            }
            for s in strengths
        ]
        ship_template = get_ship_template_config(ship["ship_id"])
        strengthen_config = get_ship_strengthen_config(ship_template["strengthen_id"])
        additions = _ship_mod_additions(ship_template["group_type"], materials)
        updates = _ship_mod_strength_updates(ship, strengthen_config, additions)

        for strength_id, exp in updates.items():
            upsert_owned_ship_strength(
                client.commander.commander_id,
                ship["id"],
                strength_id,
                exp,
            )
        consume_mod_material_ships(client.commander, material_ids)

        _apply_strength_updates(ship, updates)
        owned_ships = getattr(client.commander, "ships", [])
        client.commander.ships = [
            s for s in owned_ships
            if (s["id"] if isinstance(s, dict) else s.id) not in material_ids
        ]
        for mid in material_ids:
            owned_map.pop(mid, None)

        _send_mod_result(client, 0)
        # Server-authoritative task progress: ship enhancement consumes material
        # ships -> "Use X ships in Enhancement" (sub_type 34). Count the ships
        # actually fed as material.
        try:
            from src.answer.task_handlers import schedule_emit
            schedule_emit(client, 34, 0, len(material_ids))
        except Exception:
            pass
    except Exception as e:
        _send_mod_result(client, 1)
        return 0, 12018, e

    return 0, 12018, None
