import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

PACKET_ID = 14016


def _send_14016(client, result=0):
    asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_14016(result=result)))


def handle_transform_equipment_in_bag(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    """Gear Lab transform, source equipment sitting in the bag.

    CS_14015 { equip_id, upgrade_id } -> SC_14016 { result }. ``upgrade_id`` is
    the ``equip_upgrade_data`` formula id; the formula's ``target_id`` is what
    the commander ends up with.
    """
    if client.commander is None:
        _send_14016(client, 1)
        return 0, PACKET_ID, None

    payload = protobuf.CS_14015()
    if not payload.ParseFromString(buffer):
        _send_14016(client, 1)
        return 0, PACKET_ID, None

    equip_id = payload.equip_id
    if equip_id == 0:
        _send_14016(client, 1)
        return 0, PACKET_ID, None

    owned = client.commander.get_owned_equipment(equip_id)
    if owned is None or owned.get("count", 0) < 1:
        _send_14016(client, 1)
        return 0, PACKET_ID, None

    from src.answer.transform_equipment_common import (
        adjust_equipment_map, apply_plan, build_plan, ensure_equipment_in_map,
        equip_root, get_formula, undo_plan,
    )

    formula = get_formula(payload.upgrade_id)
    if formula is None:
        _send_14016(client, 1)
        return 0, PACKET_ID, None

    cache: dict = {}
    # The client matches the formula's `upgrade_from` against the *chain root*
    # of the source (EquipmentTransformUtil.CheckEquipmentFormulasSucceed), so
    # an already-upgraded weapon can be transformed too.
    if int(formula.get("upgrade_from", 0) or 0) != equip_root(equip_id, cache):
        _send_14016(client, 1)
        return 0, PACKET_ID, None

    plan = build_plan(client, formula, equip_id, cache)
    if plan is None:
        _send_14016(client, 1)
        return 0, PACKET_ID, None

    from src.orm.equipment import remove_owned_equipment
    from src.orm.owned_equipment import add_owned_equipment

    source_removed = False
    target_added = False
    try:
        apply_plan(client, plan)

        remove_owned_equipment(client.commander.commander_id, equip_id, 1)
        adjust_equipment_map(client, equip_id, -1)
        source_removed = True

        add_owned_equipment(client.commander.commander_id, plan["target_id"], 1)
        ensure_equipment_in_map(client, plan["target_id"], 1)
        target_added = True
    except Exception as e:
        # Never leave the commander charged for a transform that did not land.
        if target_added:
            remove_owned_equipment(client.commander.commander_id, plan["target_id"], 1)
            adjust_equipment_map(client, plan["target_id"], -1)
        if source_removed:
            add_owned_equipment(client.commander.commander_id, equip_id, 1)
            ensure_equipment_in_map(client, equip_id, 1)
        undo_plan(client, plan)
        _send_14016(client, 1)
        return 0, PACKET_ID, e

    try:
        from src.answer.task_handlers import schedule_emit
        # Handbook sub_type 46 "Develop 1 piece of gear in the Gear Lab"
        # (Rookie 22099 / Guide 23096, target_id 0, target_num 1).
        schedule_emit(client, 46, 0, 1)
    except Exception:
        pass

    _send_14016(client, 0)
    return 0, PACKET_ID, None
