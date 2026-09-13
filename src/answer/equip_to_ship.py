import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

_EQUIP_RESPONSE_ID = 12007


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


def _get_ship_equip_config(template_id: int) -> Optional[dict]:
    if template_id == 0:
        return None
    from src.orm.owned_equipment import get_ship_equip_config
    try:
        return get_ship_equip_config(template_id)
    except Exception:
        return None


def _is_forbidden_ship_type(raw, ship_type: int) -> bool:
    if not raw:
        return False
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return False
    return _contains_uint32(raw, ship_type)


def _find_ship_equipment(entries: list, pos: int) -> Optional[dict]:
    for entry in entries:
        if entry.get("pos") == pos:
            return entry
    return None


def _equipment_bag_count(commander) -> int:
    bag = getattr(commander, "owned_equipment_map", {})
    return sum(entry.get("count", 0) for entry in bag.values())


def _get_ship_type(ship: dict) -> int:
    ship_obj = ship.get("ship")
    if isinstance(ship_obj, dict):
        return ship_obj.get("type", 0)
    return getattr(ship_obj, "type", 0) if ship_obj else 0


def _send_equip_result(client, result: int):
    asyncio.create_task(client.send_message(_EQUIP_RESPONSE_ID, protobuf.SC_12007(result=result)))


def handle_equip_to_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12006.FromString(buffer)

    if payload.type != 0:
        _send_equip_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    ship_id = payload.ship_id
    ship = client.commander.owned_ships_map.get(ship_id)
    if ship is None:
        _send_equip_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    config = _get_ship_equip_config(ship.get("ship_id", 0))
    if config is None:
        _send_equip_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    slot_keys = ["equip_1", "equip_2", "equip_3", "equip_4", "equip_5"]
    slot_count = 0
    for i, key in enumerate(slot_keys):
        slot_val = config.get(key) if isinstance(config, dict) else getattr(config, key, None)
        if slot_val:
            slot_count = i + 1
    if slot_count == 0:
        slot_count = 3

    pos = payload.pos
    if isinstance(config, dict):
        slot_types = config.get(slot_keys[pos - 1], []) if 1 <= pos <= 5 else []
    else:
        slot_types = config.slot_types(pos) if hasattr(config, "slot_types") else []

    if pos == 0 or pos > slot_count or not slot_types:
        _send_equip_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    from src.orm.owned_equipment import list_owned_ship_equipment
    try:
        entries = list_owned_ship_equipment(client.commander.commander_id, ship.get("id", 0))
    except Exception as e:
        return 0, 12006, e

    current = _find_ship_equipment(entries, pos)
    if current is None:
        current = _build_ship_equipment_from_memory(client.commander.commander_id, ship, pos)

    equip_id = payload.equip_id

    if equip_id == 0:
        if current.get("equip_id", 0) == 0:
            _send_equip_result(client, 0)
            return 0, _EQUIP_RESPONSE_ID, None

        equip_bag_max = 300 + int(getattr(client.commander, "equip_bag_size", 0) or 0)
        if _equipment_bag_count(client.commander) >= equip_bag_max:
            _send_equip_result(client, 1)
            return 0, _EQUIP_RESPONSE_ID, None

        from src.orm.owned_equipment import add_owned_equipment, upsert_owned_ship_equipment
        try:
            add_owned_equipment(client.commander.commander_id, current["equip_id"], 1)
            current["equip_id"] = 0
            current["skin_id"] = 0
            upsert_owned_ship_equipment(client.commander.commander_id, current["ship_id"], current["pos"], current["equip_id"], current["skin_id"])
        except Exception as e:
            return 0, 12006, e

        _apply_ship_equipment_update(ship, current)
        _send_equip_result(client, 0)
        return 0, _EQUIP_RESPONSE_ID, None

    if current.get("equip_id", 0) == equip_id:
        _send_equip_result(client, 0)
        return 0, _EQUIP_RESPONSE_ID, None

    owned_map = getattr(client.commander, "owned_equipment_map", {})
    owned = owned_map.get(equip_id)
    if owned is None or owned.get("count", 0) == 0:
        _send_equip_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    equip_cache = {}
    equip_config = _resolve_equipment_config(equip_cache, equip_id)
    if equip_config is None:
        _send_equip_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    if not _contains_uint32(slot_types, equip_config.get("type", 0)):
        _send_equip_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    ship_type = _get_ship_type(ship)
    if _is_forbidden_ship_type(equip_config.get("ship_type_forbidden", b"[]"), ship_type):
        _send_equip_result(client, 1)
        return 0, _EQUIP_RESPONSE_ID, None

    equip_limit = equip_config.get("equip_limit", 0)
    if equip_limit != 0:
        for entry in entries:
            if entry.get("pos") == pos or entry.get("equip_id", 0) == 0:
                continue
            other_config = _resolve_equipment_config(equip_cache, entry.get("equip_id", 0))
            if other_config is not None and other_config.get("equip_limit", 0) == equip_limit:
                _send_equip_result(client, 1)
                return 0, _EQUIP_RESPONSE_ID, None

    from src.orm.owned_equipment import add_owned_equipment, upsert_owned_ship_equipment
    from src.orm.equipment import remove_owned_equipment
    try:
        if current.get("equip_id", 0) != 0:
            add_owned_equipment(client.commander.commander_id, current["equip_id"], 1)
        remove_owned_equipment(client.commander.commander_id, equip_id, 1)
        current["equip_id"] = equip_id
        current["skin_id"] = 0
        upsert_owned_ship_equipment(client.commander.commander_id, current["ship_id"], current["pos"], current["equip_id"], current["skin_id"])
    except Exception as e:
        return 0, 12006, e

    _apply_ship_equipment_update(ship, current)
    _send_equip_result(client, 0)
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 1060, 0, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    return 0, _EQUIP_RESPONSE_ID, None
