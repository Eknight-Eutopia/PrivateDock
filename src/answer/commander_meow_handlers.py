import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

COMMANDER_MEOW_RESULT_OK = 0
COMMANDER_MEOW_RESULT_FAIL = 1


BOX_BUILD_DURATIONS = {
    1: 7200,   # Rare: 2 hours
    2: 18000,  # Elite: 5 hours
    3: 36000,  # Super Rare: 10 hours
}


def handle_commander_build_box_start(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 25003
    payload = protobuf.CS_25002()
    payload.ParseFromString(buffer)

    from src.orm.commander_box import ensure_commander_boxes, upsert_commander_box
    from src.orm.commander_meow import get_commander_create_material_config

    pool_id = payload.boxid
    if pool_id not in (1, 2, 3):
        empty_box = {"box_id": 0, "pool_id": pool_id}
        return _send_commander_build_box_start_result(client, COMMANDER_MEOW_RESULT_FAIL, empty_box)

    try:
        boxes = ensure_commander_boxes(client.commander.commander_id)
    except Exception as e:
        return 0, packet_id, e

    slot_boxes = [
        b for b in boxes
        if 1 <= (b.get("box_id", b.get("id", 0)) if isinstance(b, dict) else getattr(b, "box_id", getattr(b, "id", 0))) <= 10
    ]
    slot_boxes.sort(key=lambda b: b.get("box_id", b.get("id", 0)) if isinstance(b, dict) else getattr(b, "box_id", getattr(b, "id", 0)))

    target_box = None
    for b in slot_boxes:
        p_id = b.get("pool_id", 0) if isinstance(b, dict) else getattr(b, "pool_id", 0)
        if p_id == 0:
            target_box = b
            break

    if target_box is None:
        empty_box = {"box_id": 0, "pool_id": pool_id}
        return _send_commander_build_box_start_result(client, COMMANDER_MEOW_RESULT_FAIL, empty_box)

    target_box_id = target_box.get("box_id", target_box.get("id", 0)) if isinstance(target_box, dict) else getattr(target_box, "box_id", getattr(target_box, "id", 0))

    try:
        material = get_commander_create_material_config(pool_id)
    except Exception:
        material = {}

    use_item = material.get("use_item", 20010 + pool_id)
    num_item = material.get("number_1", material.get("number1", 1))

    if hasattr(client.commander, "get_item_count"):
        cnt = client.commander.get_item_count(use_item)
        if cnt < num_item:
            empty_box = {"box_id": target_box_id, "pool_id": pool_id}
            return _send_commander_build_box_start_result(client, COMMANDER_MEOW_RESULT_FAIL, empty_box)
    if hasattr(client.commander, "consume_item"):
        try:
            client.commander.consume_item(use_item, num_item)
        except Exception:
            pass

    import time
    now = int(time.time())
    duration = BOX_BUILD_DURATIONS.get(pool_id, 7200)

    lanes = [now, now, now, now]
    active_boxes = []
    for b in slot_boxes:
        b_id = b.get("box_id", 0) if isinstance(b, dict) else getattr(b, "box_id", 0)
        if b_id == target_box_id:
            continue
        p_id = b.get("pool_id", 0) if isinstance(b, dict) else getattr(b, "pool_id", 0)
        f_time = b.get("finish_time", 0) if isinstance(b, dict) else getattr(b, "finish_time", 0)
        b_time = b.get("begin_time", 0) if isinstance(b, dict) else getattr(b, "begin_time", 0)
        if p_id != 0 and f_time > now:
            active_boxes.append((b_time, f_time, b_id))

    active_boxes.sort(key=lambda x: (x[0], x[2]))
    for b_time, f_time, b_id in active_boxes:
        lanes.sort()
        lanes[0] = max(lanes[0], f_time)

    lanes.sort()
    begin_time = max(now, lanes[0])
    finish_time = begin_time + duration

    updated_box = {
        "commander_id": client.commander.commander_id,
        "box_id": target_box_id,
        "pool_id": pool_id,
        "begin_time": begin_time,
        "finish_time": finish_time,
    }

    try:
        upsert_commander_box(updated_box)
    except Exception:
        empty_box = {"box_id": target_box_id, "pool_id": pool_id}
        return _send_commander_build_box_start_result(client, COMMANDER_MEOW_RESULT_FAIL, empty_box)

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
        template_id = roll_commander_template_for_pool(pool_id)
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
    if meow is not None:
        from src.orm.commander_meow import populate_proto_commander_info
        populate_proto_commander_info(response.commander, meow)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_commander_fleet_equip(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 25007
    payload = protobuf.CS_25006()
    payload.ParseFromString(buffer)

    cid = client.commander.commander_id
    commander_id = payload.commanderid
    if commander_id != 0:
        from src.orm.commander_meow import get_commander_meow
        try:
            m = get_commander_meow(cid, commander_id)
            if not m:
                return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)
        except Exception:
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    from src.orm.commander_meow import update_fleet_meowfficer_slot
    try:
        update_fleet_meowfficer_slot(cid, payload.groupid, payload.pos, commander_id)
    except Exception:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_OK)


def handle_commander_upgrade(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 25009
    payload = protobuf.CS_25008()
    payload.ParseFromString(buffer)

    import json
    from src.orm.commander_meow import (
        get_commander_meow,
        get_commander_template,
        get_commander_upgrade_rates,
        is_commander_meow_in_any_fleet,
        add_commander_exp,
        add_commander_skill_exp,
        update_commander_meow_level_exp,
        delete_commander_meows,
    )

    cid = client.commander.commander_id
    target_id = payload.targetid
    try:
        target = get_commander_meow(cid, target_id)
    except Exception:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    if not target:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    material_ids = list(payload.materialid)
    if not material_ids or target_id in material_ids or len(material_ids) != len(set(material_ids)):
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    target_template_id = getattr(target, "template_id", 0) if not isinstance(target, dict) else target.get("template_id", 0)
    target_tpl = get_commander_template(target_template_id)
    if not target_tpl:
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    target_group = target_tpl.get("group_type", 0)
    target_rarity = target_tpl.get("rarity", 3)
    target_max_level = target_tpl.get("max_level", 30)

    same_rate, skill_exp_val, _ = get_commander_upgrade_rates()

    materials = []
    total_gold = 0
    total_exp = 0
    total_skill_exp = 0

    for mat_id in material_ids:
        if is_commander_meow_in_any_fleet(cid, mat_id):
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

        try:
            material = get_commander_meow(cid, mat_id)
        except Exception:
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

        if not material:
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

        is_locked = getattr(material, "is_locked", 0) if not isinstance(material, dict) else material.get("is_locked", 0)
        if is_locked:
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

        mat_template_id = getattr(material, "template_id", 0) if not isinstance(material, dict) else material.get("template_id", 0)
        mat_tpl = get_commander_template(mat_template_id)
        if not mat_tpl:
            return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

        exp_cost = mat_tpl.get("exp_cost", 0)
        exp = mat_tpl.get("exp", 0)
        group_type = mat_tpl.get("group_type", 0)

        total_gold += exp_cost
        gain = exp
        if group_type == target_group and group_type != 0:
            gain = (gain * same_rate) // 10000
            total_skill_exp += skill_exp_val
        total_exp += gain
        materials.append(material)

    if not client.commander.has_enough_gold(total_gold):
        return _send_commander_simple_result(client, packet_id, COMMANDER_MEOW_RESULT_FAIL)

    try:
        client.commander.consume_resource(1, total_gold)

        cur_level = getattr(target, "level", 1) if not isinstance(target, dict) else target.get("level", 1)
        cur_exp = getattr(target, "exp", 0) if not isinstance(target, dict) else target.get("exp", 0)
        new_level, new_exp = add_commander_exp(cur_level, cur_exp, total_exp, target_rarity, target_max_level)

        skills_raw = getattr(target, "skills", None) if not isinstance(target, dict) else target.get("skills")
        if isinstance(skills_raw, str):
            try:
                skills_list = json.loads(skills_raw)
            except Exception:
                skills_list = []
        elif isinstance(skills_raw, list):
            skills_list = skills_raw
        else:
            skills_list = []
        if not skills_list:
            from src.orm.commander_meow import get_initial_commander_skills
            skills_list = get_initial_commander_skills(target_template_id)

        if total_skill_exp > 0:
            skills_list = add_commander_skill_exp(skills_list, total_skill_exp)

        target_id_val = getattr(target, "id", 0) if not isinstance(target, dict) else target.get("id", 0)
        update_commander_meow_level_exp(cid, target_id_val, new_level, new_exp, skills_list)

        mat_ids = [getattr(m, "id", 0) if not isinstance(m, dict) else m.get("id", 0) for m in materials]
        delete_commander_meows(cid, mat_ids)
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
    expected = compute_commander_quick_finish_counts(boxes, now, balance)

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
