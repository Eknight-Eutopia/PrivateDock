import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

PACKET_ID = 14014


def _send_14014(client, result=0):
    asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_14014(result=result)))


def _as_type_list(raw) -> list:
    """Ship templates carry the per-slot equipment types as ``equip_1..equip_5``;
    on some backends the JSON column comes back as a string."""
    if not raw:
        return []
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    return raw if isinstance(raw, list) else []


def handle_transform_equipment_on_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    """Gear Lab transform, source equipment equipped on a ship.

    CS_14013 { ship_id, pos, upgrade_id } -> SC_14014 { result }. ``ship_id`` is
    the owned-ship instance id, ``pos`` the 1-based slot.
    """
    if client.commander is None:
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    payload = protobuf.CS_14013()
    if not payload.ParseFromString(buffer):
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    ship_id = payload.ship_id
    pos = payload.pos
    if ship_id == 0 or pos == 0:
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    ship = client.commander.owned_ships_map.get(ship_id)
    if ship is None:
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    from src.answer.equip_to_ship import _contains_uint32, _find_ship_equipment, _is_forbidden_ship_type
    from src.answer.transform_equipment_common import (
        adjust_equipment_map, apply_plan, build_plan, ensure_equipment_in_map,
        equip_root, get_formula, undo_plan,
    )
    from src.orm.owned_equipment import (
        add_owned_equipment, apply_ship_equipment_update, get_ship_equip_config,
        list_owned_ship_equipment, resolve_equipment_config,
        upsert_owned_ship_equipment,
    )

    config = get_ship_equip_config(ship.get("ship_id", 0))
    if not isinstance(config, dict):
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    slot_keys = ["equip_1", "equip_2", "equip_3", "equip_4", "equip_5"]
    if not 1 <= pos <= len(slot_keys):
        _send_14014(client, 1)
        return 0, PACKET_ID, None
    slot_types = _as_type_list(config.get(slot_keys[pos - 1]))
    if not slot_types:
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    entries = list_owned_ship_equipment(client.commander.commander_id, ship.get("id", 0))
    current = _find_ship_equipment(entries, pos)
    if current is None:
        _send_14014(client, 1)
        return 0, PACKET_ID, None
    source_id = int(current.get("equip_id", 0) or 0)
    if source_id == 0:
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    formula = get_formula(payload.upgrade_id)
    if formula is None:
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    cache: dict = {}
    # Same check as the bag path: the formula's `upgrade_from` must be the
    # chain root of the equipment currently sitting in the slot.
    if int(formula.get("upgrade_from", 0) or 0) != equip_root(source_id, cache):
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    plan = build_plan(client, formula, source_id, cache)
    if plan is None:
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    target_id = plan["target_id"]
    target_config = resolve_equipment_config({}, target_id)
    if target_config is None:
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    # Ship.isForbiddenAtPos: the slot must accept the target's type and the
    # target must not be forbidden for this ship type. A target that no longer
    # fits goes to the bag and the slot is cleared -- the client does the same
    # locally in transformequipmentcommand.lua.
    stays_equipped = (
        _contains_uint32(slot_types, target_config.get("type", 0))
        and not _is_forbidden_ship_type(
            target_config.get("ship_type_forbidden", b"[]"),
            int(config.get("type", 0) or 0),
        )
    )
    if not stays_equipped and client.commander.equipment_bag_count() >= 4096:
        _send_14014(client, 1)
        return 0, PACKET_ID, None

    original_equip_id = int(current.get("equip_id", 0) or 0)
    original_skin_id = int(current.get("skin_id", 0) or 0)
    bagged = False
    try:
        apply_plan(client, plan)

        if stays_equipped:
            current["equip_id"] = target_id
            current["skin_id"] = 0
        else:
            add_owned_equipment(client.commander.commander_id, target_id, 1)
            ensure_equipment_in_map(client, target_id, 1)
            bagged = True
            current["equip_id"] = 0
            current["skin_id"] = 0

        upsert_owned_ship_equipment(
            current["owner_id"], current["ship_id"], current["pos"],
            current["equip_id"], current["skin_id"],
        )
    except Exception as e:
        # Never leave the commander charged for a transform that did not land.
        try:
            upsert_owned_ship_equipment(
                current["owner_id"], current["ship_id"], current["pos"],
                original_equip_id, original_skin_id,
            )
            if bagged:
                from src.orm.equipment import remove_owned_equipment
                remove_owned_equipment(client.commander.commander_id, target_id, 1)
                adjust_equipment_map(client, target_id, -1)
        except Exception:
            pass
        undo_plan(client, plan)
        _send_14014(client, 1)
        return 0, PACKET_ID, e

    apply_ship_equipment_update(ship, current)

    try:
        from src.answer.task_handlers import schedule_emit
        # Handbook sub_type 46 "Develop 1 piece of gear in the Gear Lab"
        # (Rookie 22099 / Guide 23096, target_id 0, target_num 1).
        schedule_emit(client, 46, 0, 1)
    except Exception:
        pass

    _send_14014(client, 0)
    return 0, PACKET_ID, None
