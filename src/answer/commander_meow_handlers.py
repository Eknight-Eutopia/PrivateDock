import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

COMMANDER_MEOW_RESULT_OK = 0
COMMANDER_MEOW_RESULT_FAIL = 1


def handle_commander_build_box_start(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 25003
    payload = protobuf.CS_25002()
    payload.ParseFromString(buffer)

    from src.orm.commander_box import ensure_commander_boxes, get_commander_box
    from src.orm.commander_meow import get_commander_create_material_config

    try:
        ensure_commander_boxes(client.commander.commander_id)
    except Exception as e:
        return 0, packet_id, e

    try:
        box = get_commander_box(client.commander.commander_id, payload.boxid)
    except Exception:
        empty_box = {"box_id": payload.boxid}
        return _send_commander_build_box_start_result(client, COMMANDER_MEOW_RESULT_FAIL, empty_box)

    if isinstance(box, dict):
        pool_id = box.get("pool_id", 0)
    else:
        pool_id = getattr(box, "pool_id", 0)

    if pool_id != 0:
        return _send_commander_build_box_start_result(client, COMMANDER_MEOW_RESULT_FAIL, box)

    try:
        material = get_commander_create_material_config()
    except Exception:
        return _send_commander_build_box_start_result(client, COMMANDER_MEOW_RESULT_FAIL, box)

    import time
    now = int(time.time())
    updated_box = {
        "commander_id": client.commander.commander_id,
        "box_id": payload.boxid,
        "pool_id": payload.boxid,
        "begin_time": now,
        "finish_time": now + 3600,
    }

    from src.orm.commander_box import upsert_commander_box
    try:
        client.commander.consume_item(material.get("use_item", 0), material.get("number1", 0))
        upsert_commander_box(updated_box)
    except Exception:
        return _send_commander_build_box_start_result(client, COMMANDER_MEOW_RESULT_FAIL, box)

    return _send_commander_build_box_start_result(client, COMMANDER_MEOW_RESULT_OK, updated_box)


def _send_commander_build_box_start_result(client: Client, result: int, box) -> tuple[int, int, Optional[Exception]]:
    packet_id = 25003
    response = protobuf.SC_25003(result=result)
    box_entry = protobuf.COMMANDERBOXINFO()
    if isinstance(box, dict):
        box_entry.id = box.get("box_id", box.get("id", 0))
        box_entry.poolId = box.get("pool_id", 0)
        box_entry.finish_time = box.get("finish_time", 0)
        box_entry.begin_time = box.get("begin_time", 0)
    else:
        box_entry.id = getattr(box, "box_id", getattr(box, "id", 0))
        box_entry.poolId = getattr(box, "pool_id", 0)
        box_entry.finish_time = getattr(box, "finish_time", 0)
        box_entry.begin_time = getattr(box, "begin_time", 0)
    response.box.CopyFrom(box_entry)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_commander_claim_box(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 25005
    payload = protobuf.CS_25004()
    payload.ParseFromString(buffer)

    from src.orm.commander_box import ensure_commander_boxes, get_commander_box
    from src.orm.commander_meow import list_commander_meows

    try:
        ensure_commander_boxes(client.commander.commander_id)
    except Exception as e:
        return 0, packet_id, e

    try:
        box = get_commander_box(client.commander.commander_id, payload.boxid)
    except Exception:
        return _send_commander_claim_box_result(client, COMMANDER_MEOW_RESULT_FAIL, None, 0)

    import time
    now = int(time.time())

    if isinstance(box, dict):
        pool_id = box.get("pool_id", 0)
        finish_time = box.get("finish_time", 0)
    else:
        pool_id = getattr(box, "pool_id", 0)
        finish_time = getattr(box, "finish_time", 0)

    if pool_id == 0 or finish_time > now:
        return _send_commander_claim_box_result(client, COMMANDER_MEOW_RESULT_FAIL, None, finish_time)

    try:
        current = list_commander_meows(client.commander.commander_id)
    except Exception as e:
        return 0, packet_id, e

    if len(current) >= 200:
        return _send_commander_claim_box_result(client, COMMANDER_MEOW_RESULT_FAIL, None, finish_time)

    from src.orm.commander_meow import roll_commander_template_for_pool
    try:
        template_id = roll_commander_template_for_pool()
    except Exception:
        return _send_commander_claim_box_result(client, COMMANDER_MEOW_RESULT_FAIL, None, finish_time)

    from src.orm.commander_box import upsert_commander_box
    from src.orm.commander_meow import create_commander_meow
    try:
        meow = create_commander_meow(client.commander.commander_id, template_id)
        if isinstance(box, dict):
            box["pool_id"] = 0
            box["begin_time"] = 0
            box["finish_time"] = 0
        else:
            box.pool_id = 0
            box.begin_time = 0
            box.finish_time = 0
        upsert_commander_box(box)
    except Exception:
        return _send_commander_claim_box_result(client, COMMANDER_MEOW_RESULT_FAIL, None, finish_time)

    # Server-authoritative task progress: claiming a built Meowfficer box
    # advances "Train N Meowfficer" (sub_type 170).
    try:
        from src.answer.task_handlers import schedule_emit
        schedule_emit(client, 170, 0, 1)
    except Exception:
        pass

    return _send_commander_claim_box_result(client, COMMANDER_MEOW_RESULT_OK, meow, now)


def _send_commander_claim_box_result(client: Client, result: int, meow, finish_time: int) -> tuple[int, int, Optional[Exception]]:
    packet_id = 25005
    response = protobuf.SC_25005(result=result, finish_time=finish_time)
    cmd_entry = protobuf.COMMANDERINFO()
    if meow is not None:
        if isinstance(meow, dict):
            cmd_entry.id = meow.get("id", 0)
            cmd_entry.template_id = meow.get("template_id", 0)
            cmd_entry.level = meow.get("level", 0)
            cmd_entry.exp = meow.get("exp", 0)
            cmd_entry.is_locked = meow.get("is_locked", 0)
            cmd_entry.ability.extend(meow.get("ability", []))
            cmd_entry.ability_origin.extend(meow.get("ability_origin", []))
            cmd_entry.ability_time = meow.get("ability_time", 0)
            cmd_entry.used_pt = meow.get("used_pt", 0)
            cmd_entry.name = meow.get("name", "")
            cmd_entry.rename_time = meow.get("rename_time", 0)
        else:
            cmd_entry.id = getattr(meow, "id", 0)
            cmd_entry.template_id = getattr(meow, "template_id", 0)
            cmd_entry.level = getattr(meow, "level", 0)
            cmd_entry.exp = getattr(meow, "exp", 0)
            cmd_entry.is_locked = getattr(meow, "is_locked", 0)
            cmd_entry.ability.extend(getattr(meow, "ability", []) or [])
            cmd_entry.ability_origin.extend(getattr(meow, "ability_origin", []) or [])
            cmd_entry.ability_time = getattr(meow, "ability_time", 0)
            cmd_entry.used_pt = getattr(meow, "used_pt", 0)
            cmd_entry.name = getattr(meow, "name", "")
            cmd_entry.rename_time = getattr(meow, "rename_time", 0)
    response.commander.CopyFrom(cmd_entry)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_commander_fleet_equip(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 25007
    payload = protobuf.CS_25006()
    payload.ParseFromString(buffer)

    commander_id = payload.commanderid
    if commander_id != 0:
        from src.orm.commander_meow import get_commander_meow
        try:
            get_commander_meow(client.commander.commander_id, commander_id)
        except Exception:
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    from src.orm.commander_meow import update_fleet_meowfficer_slot
    try:
        update_fleet_meowfficer_slot(client.commander, payload.groupid, payload.pos, commander_id)
    except Exception:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_OK)


def handle_commander_upgrade(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 25009
    payload = protobuf.CS_25008()
    payload.ParseFromString(buffer)

    from src.orm.commander_meow import get_commander_meow, get_commander_data_template_config
    from src.orm.commander_meow import get_commander_upgrade_rates

    target_id = payload.targetid
    try:
        target = get_commander_meow(client.commander.commander_id, target_id)
    except Exception:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    material_ids = list(payload.materialid)
    if not material_ids:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    if target_id in material_ids:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    if isinstance(target, dict):
        target_template_id = target.get("template_id", 0)
    else:
        target_template_id = getattr(target, "template_id", 0)

    try:
        target_tpl = get_commander_data_template_config()
    except Exception:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    same_rate, _, _ = get_commander_upgrade_rates()

    seen = set()
    materials = []
    total_gold = 0
    total_exp = 0

    for material_id in material_ids:
        if material_id in seen:
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)
        seen.add(material_id)

        from src.orm.players import is_commander_in_any_fleet
        if is_commander_in_any_fleet(client.commander, material_id):
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

        try:
            material = get_commander_meow(client.commander.commander_id, material_id)
        except Exception:
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

        if isinstance(material, dict):
            mat_template_id = material.get("template_id", 0)
        else:
            mat_template_id = getattr(material, "template_id", 0)

        try:
            material_tpl = get_commander_data_template_config()
        except Exception:
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

        if isinstance(material_tpl, dict):
            exp_cost = material_tpl.get("exp_cost", 0)
            exp = material_tpl.get("exp", 0)
            group_type = material_tpl.get("group_type", 0)
        else:
            exp_cost = getattr(material_tpl, "exp_cost", 0)
            exp = getattr(material_tpl, "exp", 0)
            group_type = getattr(material_tpl, "group_type", 0)

        total_gold += exp_cost
        gain = exp
        if isinstance(target_tpl, dict):
            target_group = target_tpl.get("group_type", 0)
        else:
            target_group = getattr(target_tpl, "group_type", 0)

        if group_type == target_group:
            gain = (gain * same_rate) // 10000
        total_exp += gain
        materials.append(material)

    if not client.commander.has_enough_gold(total_gold):
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    from src.orm.commander_meow import update_commander_meow_exp, delete_commander_meows
    try:
        client.commander.consume_resource(1, total_gold)
        if isinstance(target, dict):
            target_exp = target.get("exp", 0)
            target_id_val = target.get("id", 0)
        else:
            target_exp = getattr(target, "exp", 0)
            target_id_val = target.id
        update_commander_meow_exp(client.commander.commander_id, target_id_val, target_exp + total_exp)
        mat_ids = []
        for m in materials:
            mat_ids.append(m.get("id", 0) if isinstance(m, dict) else m.id)
        delete_commander_meows(client.commander.commander_id, mat_ids)
    except Exception:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_OK)


def handle_commander_quickly_finish_boxes(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 25038
    payload = protobuf.CS_25037()
    payload.ParseFromString(buffer)

    from src.orm.commander_box import ensure_commander_boxes
    from src.orm.commander_meow import compute_commander_quick_finish_counts

    try:
        boxes = ensure_commander_boxes(client.commander.commander_id)
    except Exception as e:
        return 0, packet_id, e

    import time
    now = int(time.time())
    balance = client.commander.get_item_count(20010)
    expected = compute_commander_quick_finish_counts()

    if expected.get("item_cnt", 0) == 0:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    if (payload.item_cnt != expected.get("item_cnt", 0)
            or payload.finish_cnt != expected.get("finish_cnt", 0)
            or payload.affect_cnt != expected.get("affect_cnt", 0)):
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    from src.orm.commander_meow import apply_commander_quick_finish
    try:
        client.commander.consume_item(20010, expected.get("item_cnt", 0))
        apply_commander_quick_finish(boxes, now, expected.get("item_cnt", 0))
    except Exception:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_OK)


def _send_commander_simple_result(client: Client, result_packet_id: int, result: int) -> tuple[int, int, Optional[Exception]]:
    packet_id = result_packet_id
    response = protobuf.SC_25007(result=result) if result_packet_id == 25007 else \
               protobuf.SC_25009(result=result) if result_packet_id == 25009 else \
               protobuf.SC_25038(result=result) if result_packet_id == 25038 else \
               {"result": result}
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
