import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def _contains_uint32(lst: list, val: int) -> bool:
    for entry in lst:
        if entry == val:
            return True
    return False


from src.orm.owned_equipment import (
    build_ship_equipment_from_memory as _build_ship_equipment_from_memory,
    apply_ship_equipment_update as _apply_ship_equipment_update,
    resolve_equipment_config as _resolve_equipment_config,
)


def _send_skin_result(client, result: int):
    asyncio.create_task(client.send_message(12037, protobuf.SC_12037(result=result)))


def handle_update_ship_equipment_skin(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12036()
    try:
        if not payload.ParseFromString(buffer):
            _send_skin_result(client, 1)
            return 0, 12037, None
    except Exception:
        _send_skin_result(client, 1)
        return 0, 12037, None

    ship_id = payload.ship_id
    owned_map = getattr(client.commander, "owned_ships_map", {})
    ship = owned_map.get(ship_id)
    if ship is None:
        _send_skin_result(client, 1)
        return 0, 12037, None

    from src.orm.owned_equipment import get_ship_equip_config
    try:
        config = get_ship_equip_config(ship.get("ship_id", 0))
    except Exception as e:
        return 0, 12037, e

    if isinstance(config, dict):
        slot_keys = ["equip_1", "equip_2", "equip_3", "equip_4", "equip_5"]
        slot_count = 0
        for i, key in enumerate(slot_keys):
            if config.get(key):
                slot_count = i + 1
        if slot_count == 0:
            slot_count = 3
        pos = payload.pos
        slot_types = config.get(slot_keys[pos - 1], []) if 1 <= pos <= 5 else []
    else:
        slot_count = config.slot_count() if hasattr(config, "slot_count") else 3
        pos = payload.pos
        slot_types = config.slot_types(pos) if hasattr(config, "slot_types") else []

    if pos == 0 or pos > slot_count or not slot_types:
        _send_skin_result(client, 1)
        return 0, 12037, None

    from src.orm.equipment import get_owned_ship_equipment
    from src.db.store import NotFoundError
    try:
        current = get_owned_ship_equipment(ship.get("id", 0), pos)
        if current is None:
            current = _build_ship_equipment_from_memory(client.commander.commander_id, ship, pos)
        else:
            current = {
                "owner_id": current.get("owner_id", client.commander.commander_id),
                "ship_id": current.get("ship_id", ship.get("id", 0)),
                "pos": current.get("pos", pos),
                "equip_id": current.get("equip_id", 0),
                "skin_id": current.get("skin_id", 0),
            }
    except NotFoundError:
        current = _build_ship_equipment_from_memory(client.commander.commander_id, ship, pos)
    except Exception as e:
        return 0, 12037, e

    skin_id = payload.equip_skin_id
    if skin_id != 0:
        if current.get("equip_id", 0) == 0:
            _send_skin_result(client, 1)
            return 0, 12037, None

        equip_cache = {}
        equip_config = _resolve_equipment_config(equip_cache, current.get("equip_id", 0))
        if equip_config is None:
            _send_skin_result(client, 1)
            return 0, 12037, None

        equip_type = equip_config.get("type", 0)

        from src.orm.config_entry import get_config_entry
        try:
            raw = get_config_entry("ShareCfg/equip_skin_template.json", str(skin_id))
        except NotFoundError:
            _send_skin_result(client, 1)
            return 0, 12037, None
        except Exception as e:
            return 0, 12037, e
        raw = getattr(raw, "data", raw)
        template = raw if isinstance(raw, dict) else json.loads(raw) if isinstance(raw, str) else {}
        equip_types = template.get("equip_type", [])
        if not equip_types or not _contains_uint32(equip_types, equip_type):
            _send_skin_result(client, 1)
            return 0, 12037, None

        from src.orm.equipment_skin import get_equip_skin_count_sync
        try:
            owned_count = get_equip_skin_count_sync(client.commander.commander_id, skin_id)
        except Exception as e:
            return 0, 12037, e
        if owned_count < 1:
            _send_skin_result(client, 1)
            return 0, 12037, None

    if current.get("skin_id", 0) == skin_id:
        _send_skin_result(client, 0)
        return 0, 12037, None

    old_skin_id = current.get("skin_id", 0)
    current["skin_id"] = skin_id
    from src.orm.owned_equipment import upsert_owned_ship_equipment
    try:
        upsert_owned_ship_equipment(current["owner_id"], current["ship_id"], current["pos"], current["equip_id"], current["skin_id"])
    except Exception as e:
        return 0, 12037, e

    # Mirror the client's local stock changes (apply consumes the new skin,
    # the previous one goes back; unload just returns the old skin).
    from src.orm.equipment_skin import consume_equip_skin_sync, grant_equip_skin_sync
    try:
        if skin_id != 0:
            consume_equip_skin_sync(client.commander.commander_id, skin_id, 1)
        if old_skin_id != 0 and old_skin_id != skin_id:
            grant_equip_skin_sync(client.commander.commander_id, old_skin_id, 1)
    except Exception as e:
        return 0, 12037, e

    _apply_ship_equipment_update(ship, current)
    _send_skin_result(client, 0)
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 47, 0, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    return 0, 12037, None
