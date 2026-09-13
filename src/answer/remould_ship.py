import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def _find_remould_target(options: list, current: int) -> Optional[int]:
    for entry in options:
        if len(entry) < 2:
            continue
        if entry[0] == current:
            return entry[1]
    return None


def _find_transform_level(transforms: list, transform_id: int) -> int:
    for entry in transforms:
        if entry.get("transform_id") == transform_id:
            return entry.get("level", 0)
    return 0


def _remould_items_for_next_level(config: dict, current_level: int) -> list:
    use_item = config.get("use_item") or []
    if current_level >= len(use_item):
        return []
    raw = use_item[current_level]
    if not raw:
        return []
    items = []
    for entry in raw:
        if len(entry) < 2:
            raise Exception("invalid remould item entry")
        items.append({"id": entry[0], "count": entry[1]})
    return items


def _remould_prerequisites_met(transforms: list, prereq_ids: list) -> bool:
    if not prereq_ids:
        return True
    from src.orm.game_data import get_transform_data_template

    for prereq_id in prereq_ids:
        level = _find_transform_level(transforms, prereq_id)
        prereq_config = get_transform_data_template(prereq_id)
        if prereq_config is None:
            return False
        if level != prereq_config.get("max_level", 0):
            return False
    return True


def _apply_transform_update(ship: dict, transform_id: int, level: int):
    transforms = ship.get("transforms", [])
    for entry in transforms:
        if entry.get("transform_id") == transform_id:
            entry["level"] = level
            return
    transforms.append({
        "owner_id": ship.get("owner_id", 0),
        "ship_id": ship.get("id", 0),
        "transform_id": transform_id,
        "level": level,
    })


def _remove_transforms(ship: dict, transform_ids: list):
    if not transform_ids:
        return
    id_set = set(transform_ids)
    ship["transforms"] = [t for t in ship.get("transforms", []) if t.get("transform_id") not in id_set]


def _normalize_transforms_list(value) -> list:
    if isinstance(value, dict):
        return []
    return list(value or [])


def _send_remould_result(client, result: int):
    asyncio.create_task(client.send_message(12012, protobuf.SC_12012(result=result)))


def handle_remould_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12011()
    payload.ParseFromString(buffer)

    ship_id = payload.ship_id
    owned_map = getattr(client.commander, "owned_ships_map", {})
    ship = owned_map.get(ship_id)
    if ship is None:
        _send_remould_result(client, 1)
        return 0, 12012, None

    try:
        from src.orm.game_data import get_transform_data_template, get_ship_template_config
        from src.orm.owned_ship_transform import upsert_owned_ship_transform, delete_owned_ship_transforms
        from src.orm.owned_ship import (
            get_owned_ship_transforms,
            update_owned_ship_ship_id_skin_id,
            consume_mod_material_ships,
        )
        from src.orm.skin import give_skin

        config = get_transform_data_template(payload.remould_id)
        if config is None:
            _send_remould_result(client, 1)
            return 0, 12012, None

        ship_id_config = _normalize_transforms_list(config.get("ship_id"))
        if ship_id_config:
            target_template_id = _find_remould_target(ship_id_config, ship.get("ship_id", 0))
            if target_template_id is None:
                _send_remould_result(client, 1)
                return 0, 12012, None
        else:
            target_template_id = ship.get("ship_id", 0)

        transform_rows = get_owned_ship_transforms(client.commander.commander_id)
        ship["transforms"] = [
            {
                "owner_id": t.owner_id,
                "ship_id": t.ship_id,
                "transform_id": t.transform_id,
                "level": t.level,
            }
            for t in transform_rows
            if t.ship_id == ship["id"]
        ]

        current_level = _find_transform_level(ship["transforms"], config.get("id", 0))
        if current_level >= config.get("max_level", 0):
            _send_remould_result(client, 1)
            return 0, 12012, None

        if ship.get("level", 0) < config.get("level_limit", 0):
            _send_remould_result(client, 1)
            return 0, 12012, None

        ship_template = get_ship_template_config(ship.get("ship_id", 0))
        star = (ship_template or {}).get("star", 0)
        if star < config.get("star_limit", 0):
            _send_remould_result(client, 1)
            return 0, 12012, None

        if not client.commander.has_enough_gold(config.get("use_gold", 0)):
            _send_remould_result(client, 1)
            return 0, 12012, None

        items = _remould_items_for_next_level(config, current_level)
        for item in items:
            if not client.commander.has_enough_item(item["id"], item["count"]):
                _send_remould_result(client, 1)
                return 0, 12012, None

        if not _remould_prerequisites_met(ship["transforms"], _normalize_transforms_list(config.get("condition_id"))):
            _send_remould_result(client, 1)
            return 0, 12012, None

        material_ids = list(payload.material_id)
        use_ship = config.get("use_ship", 0)
        if use_ship == 0:
            if len(material_ids) != 0:
                _send_remould_result(client, 1)
                return 0, 12012, None
        else:
            if len(material_ids) != use_ship:
                _send_remould_result(client, 1)
                return 0, 12012, None
            for material_id in material_ids:
                if material_id == ship["id"]:
                    _send_remould_result(client, 1)
                    return 0, 12012, None
                if material_id not in owned_map:
                    _send_remould_result(client, 1)
                    return 0, 12012, None

        client.commander.consume_resource(1, config.get("use_gold", 0))
        for item in items:
            client.commander.consume_item(item["id"], item["count"])

        upsert_owned_ship_transform(
            client.commander.commander_id,
            ship["id"],
            config.get("id", 0),
            current_level + 1,
        )
        edit_trans = _normalize_transforms_list(config.get("edit_trans"))
        delete_owned_ship_transforms(
            client.commander.commander_id,
            ship["id"],
            edit_trans,
        )
        skin_id = config.get("skin_id", 0)
        if skin_id != 0:
            give_skin(client.commander.commander_id, skin_id)

        update_owned_ship_ship_id_skin_id(
            client.commander.commander_id,
            ship["id"],
            target_template_id,
            skin_id if skin_id != 0 else ship.get("skin_id", 0),
        )

        if material_ids:
            consume_mod_material_ships(client.commander, material_ids)

        _apply_transform_update(ship, config.get("id", 0), current_level + 1)
        ship["ship_id"] = target_template_id
        if skin_id != 0:
            ship["skin_id"] = skin_id
        _remove_transforms(ship, edit_trans)
        if material_ids:
            for mid in material_ids:
                owned_map.pop(mid, None)

        _send_remould_result(client, 0)
        # Server-authoritative task progress: a successful retrofit upgrade
        # advances "Perform X retrofit upgrades" (sub_type 1018).
        try:
            from src.answer.task_handlers import schedule_emit
            schedule_emit(client, 1018, 0, 1)
        except Exception:
            pass
    except Exception as e:
        _send_remould_result(client, 1)
        return 0, 12012, e

    return 0, 12012, None