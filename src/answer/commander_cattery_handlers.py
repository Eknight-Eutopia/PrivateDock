import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

COMMANDER_RESULT_OK = 0
COMMANDER_RESULT_ERROR = 1

COMMANDER_CATTERY_ALL_OPS = 1 | 2 | 4


def handle_commander_cattery_operation(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25028()
    payload.ParseFromString(buffer)
    op_type = payload.type

    response = protobuf.SC_25029(result=COMMANDER_RESULT_ERROR, level=0, exp=0, op_time=0)

    try:
        from src.orm import (
            CommanderCatteryOpBit as _opbit,
            CommanderCatteryOpFeed as _opfeed,
            CommanderCatteryOpClean as _opclean,
        )
        from src.orm.commander_home import ensure_commander_home, update_commander_home_slot, get_commander_home_feed_exp, update_commander_home
        from src.orm import commander_has_cattery_op_flag, commander_clear_cattery_op_flag
        op_bit = _opbit(op_type)
        if op_bit == 0:
            asyncio.create_task(client.send_message(25029, response))
            return 0, 25029, None

        home, slots = ensure_commander_home(client.commander.commander_id)
        if isinstance(home, dict):
            response.level = home.get("level", 0)
            response.exp = home.get("exp", 0)
        else:
            response.level = getattr(home, "level", 0)
            response.exp = getattr(home, "exp", 0)

        now = int(asyncio.get_event_loop().time())

        eligible = []
        for slot in slots:
            if isinstance(slot, dict):
                if slot.get("assigned_commander_id", 0) == 0:
                    continue
                if not commander_has_cattery_op_flag(slot.get("op_flag", 0), op_type):
                    continue
                if not _commander_supports_operation(slot.get("assigned_commander_id", 0), op_type):
                    continue
            else:
                if getattr(slot, "assigned_commander_id", 0) == 0:
                    continue
                if not commander_has_cattery_op_flag(getattr(slot, "op_flag", 0), op_type):
                    continue
                if not _commander_supports_operation(getattr(slot, "assigned_commander_id", 0), op_type):
                    continue
            eligible.append(slot)

        if not eligible:
            asyncio.create_task(client.send_message(25029, response))
            return 0, 25029, None

        for slot in eligible:
            if isinstance(slot, dict):
                slot["op_flag"] = commander_clear_cattery_op_flag(slot.get("op_flag", 0), op_type)
                slot["exp_time"] = now
                slot["cache_exp"] = 0
            else:
                slot.op_flag = commander_clear_cattery_op_flag(getattr(slot, "op_flag", 0), op_type)
                slot.exp_time = now
                slot.cache_exp = 0
            update_commander_home_slot(slot)

            if op_type == _opfeed:
                assigned_id = slot.get("assigned_commander_id", 0) if isinstance(slot, dict) else getattr(slot, "assigned_commander_id", 0)
                ships_map = getattr(client.commander, "ships_map", {}) or getattr(client.commander, "owned_ships_map", {})
                assigned = ships_map.get(assigned_id)
                if assigned:
                    feed_exp = get_commander_home_feed_exp(response.level)
                    if feed_exp > 0:
                        _apply_owned_ship_commander_exp(assigned, feed_exp)

        if op_type == _opclean:
            if isinstance(home, dict):
                home["clean"] = home.get("clean", 0) + 1
            else:
                home.clean = getattr(home, "clean", 0) + 1
            update_commander_home(home)
            if isinstance(home, dict):
                response.level = home.get("level", 0)
                response.exp = home.get("exp", 0)
            else:
                response.level = getattr(home, "level", 0)
                response.exp = getattr(home, "exp", 0)

        response.result = COMMANDER_RESULT_OK
        response.op_time = now
    except (ImportError, AttributeError):
        pass

    asyncio.create_task(client.send_message(25029, response))
    return 0, 25029, None


def handle_commander_cattery_assign(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25030()
    payload.ParseFromString(buffer)

    response = protobuf.SC_25031(result=COMMANDER_RESULT_ERROR, time=0, commander_level=0, commander_exp=0)

    try:
        from src.orm import (
            CommanderCatteryOpBit as _opbit,
        )
        from src.orm.commander_home import ensure_commander_home, update_commander_home_slot

        home, slots = ensure_commander_home(client.commander.commander_id)

        slot_index = payload.slotidx
        if slot_index == 0 or slot_index > len(slots):
            asyncio.create_task(client.send_message(25031, response))
            return 0, 25031, None

        slot = slots[slot_index - 1]
        now = int(asyncio.get_event_loop().time())

        if isinstance(slot, dict):
            assigned_id = slot.get("assigned_commander_id", 0)
        else:
            assigned_id = getattr(slot, "assigned_commander_id", 0)

        if assigned_id != 0:
            ships_map = getattr(client.commander, "ships_map", {}) or getattr(client.commander, "owned_ships_map", {})
            assigned = ships_map.get(assigned_id)
            if assigned:
                if isinstance(assigned, dict):
                    response.commander_level = assigned.get("level", 0)
                    response.commander_exp = assigned.get("exp", 0)
                else:
                    response.commander_level = getattr(assigned, "level", 0)
                    response.commander_exp = getattr(assigned, "exp", 0)

        new_commander_id = payload.commander_id

        if new_commander_id == 0:
            if assigned_id == 0:
                asyncio.create_task(client.send_message(25031, response))
                return 0, 25031, None
            if isinstance(slot, dict):
                slot["assigned_commander_id"] = 0
                slot["exp_time"] = now
            else:
                slot.assigned_commander_id = 0
                slot.exp_time = now
            update_commander_home_slot(slot)
            response.result = COMMANDER_RESULT_OK
            response.time = now
            asyncio.create_task(client.send_message(25031, response))
            return 0, 25031, None

        ships_map = getattr(client.commander, "ships_map", {}) or getattr(client.commander, "owned_ships_map", {})
        if new_commander_id not in ships_map:
            asyncio.create_task(client.send_message(25031, response))
            return 0, 25031, None

        for s in slots:
            target_id = s.get("assigned_commander_id", 0) if isinstance(s, dict) else getattr(s, "assigned_commander_id", 0)
            slot_id = s.get("slot_id", 0) if isinstance(s, dict) else getattr(s, "slot_id", 0)
            my_slot_id = slot.get("slot_id", 0) if isinstance(slot, dict) else getattr(slot, "slot_id", 0)
            if slot_id == my_slot_id:
                continue
            if target_id == new_commander_id:
                asyncio.create_task(client.send_message(25031, response))
                return 0, 25031, None

        if isinstance(slot, dict):
            slot["assigned_commander_id"] = new_commander_id
            slot["exp_time"] = now
            slot["op_flag"] = COMMANDER_CATTERY_ALL_OPS & _commander_operation_mask_for_commander(new_commander_id)
        else:
            slot.assigned_commander_id = new_commander_id
            slot.exp_time = now
            slot.op_flag = COMMANDER_CATTERY_ALL_OPS & _commander_operation_mask_for_commander(new_commander_id)
        update_commander_home_slot(slot)
        response.result = COMMANDER_RESULT_OK
        response.time = now
        # Server-authoritative task progress: assigning a Meowfficer to a
        # Comf-Fort slot advances the cattery task (sub_type 171).
        try:
            from src.answer.task_handlers import schedule_emit
            schedule_emit(client, 171, 0, 1)
        except Exception:
            pass
    except (ImportError, AttributeError):
        pass

    asyncio.create_task(client.send_message(25031, response))
    return 0, 25031, None


def handle_commander_cattery_style(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25032()
    payload.ParseFromString(buffer)

    response = protobuf.SC_25033(result=COMMANDER_RESULT_ERROR)

    try:
        from src.orm.commander_home import ensure_commander_home, update_commander_home_slot, get_commander_home_style_list
        from src.orm.config_entry import get_config_entry

        home, slots = ensure_commander_home(client.commander.commander_id)

        slot_index = payload.slotidx
        if slot_index == 0 or slot_index > len(slots):
            asyncio.create_task(client.send_message(25033, response))
            return 0, 25033, None

        style_id = payload.styleidx
        home_level = home.get("level", 0) if isinstance(home, dict) else getattr(home, "level", 0)

        if not _is_commander_home_style_allowed(home_level, style_id):
            asyncio.create_task(client.send_message(25033, response))
            return 0, 25033, None

        if not _is_commander_home_style_known(style_id):
            asyncio.create_task(client.send_message(25033, response))
            return 0, 25033, None

        slot = slots[slot_index - 1]
        if isinstance(slot, dict):
            if slot.get("style", 0) != style_id:
                slot["style"] = style_id
                update_commander_home_slot(slot)
        else:
            if getattr(slot, "style", 0) != style_id:
                slot.style = style_id
                update_commander_home_slot(slot)

        response.result = COMMANDER_RESULT_OK
    except (ImportError, AttributeError):
        pass

    asyncio.create_task(client.send_message(25033, response))
    return 0, 25033, None


def handle_commander_cattery_scene_state(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25036()
    payload.ParseFromString(buffer)

    try:
        from src.orm.commander_home import ensure_commander_home, clear_commander_home_cache_exp, update_commander_home

        home, _ = ensure_commander_home(client.commander.commander_id)
        is_open = payload.is_open

        if is_open == 0:
            if isinstance(home, dict):
                home["scene_open"] = True
            else:
                home.scene_open = True
            clear_commander_home_cache_exp(client.commander.commander_id)
        elif is_open == 1:
            if isinstance(home, dict):
                home["scene_open"] = False
            else:
                home.scene_open = False
        else:
            return 0, 0, None

        update_commander_home(home)
    except (ImportError, AttributeError):
        pass

    return 0, 0, None


def handle_commander_boxes_refresh(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25034()
    payload.ParseFromString(buffer)

    response = protobuf.SC_25035()

    try:
        from src.orm.commander_box import ensure_commander_boxes, to_proto_commander_box
        boxes = ensure_commander_boxes(client.commander.commander_id)
        for box in boxes:
            box_entry = protobuf.COMMANDERBOXINFO()
            if isinstance(box, dict):
                box_entry.id = box.get("id", 0)
                box_entry.poolId = box.get("pool_id", 0)
                box_entry.finish_time = box.get("finish_time", 0)
                box_entry.begin_time = box.get("begin_time", 0)
            else:
                box_entry.id = box.id
                box_entry.poolId = box.pool_id
                box_entry.finish_time = box.finish_time
                box_entry.begin_time = box.begin_time
            response.box_list.append(box_entry)
    except (ImportError, AttributeError):
        pass

    asyncio.create_task(client.send_message(25035, response))
    return 0, 25035, None


def _commander_operation_mask_for_commander(commander_id: int) -> int:
    try:
        from src.orm.config_entry import get_config_entry
        entry = get_config_entry("ShareCfg/commander_data_template.json", str(commander_id))
        if entry:
            data = entry.get("data", "{}") if isinstance(entry, dict) else getattr(entry, "data", "{}")
            if isinstance(data, str):
                payload = json.loads(data)
            else:
                payload = data
            ability = payload.get("ability", [])
            if ability:
                from src.orm import CommanderCatteryOpBit as _opbit
                mask = 0
                for op_type in ability:
                    mask |= _opbit(op_type)
                return mask if mask != 0 else COMMANDER_CATTERY_ALL_OPS
    except Exception:
        pass
    return COMMANDER_CATTERY_ALL_OPS


def _commander_supports_operation(commander_id: int, op_type: int) -> bool:
    try:
        from src.orm import commander_has_cattery_op_flag
        return commander_has_cattery_op_flag(
            _commander_operation_mask_for_commander(commander_id), op_type,
        )
    except Exception:
        return True


def _apply_owned_ship_commander_exp(owned, gain: int) -> None:
    if gain == 0:
        return
    max_level = owned.get("max_level", 0) if isinstance(owned, dict) else getattr(owned, "max_level", 0)
    level = owned.get("level", 0) if isinstance(owned, dict) else getattr(owned, "level", 0)
    exp = owned.get("exp", 0) if isinstance(owned, dict) else getattr(owned, "exp", 0)

    if level >= max_level:
        return

    exp = exp + gain
    while exp >= 100 and level < max_level:
        exp -= 100
        level += 1

    if level >= max_level:
        exp = 0

    if isinstance(owned, dict):
        owned["exp"] = exp
        owned["level"] = level
    else:
        owned.exp = exp
        owned.level = level

    try:
        owned.update()
    except Exception:
        pass


def _is_commander_home_style_allowed(level: int, style_id: int) -> bool:
    try:
        from src.orm.commander_home import get_commander_home_style_list
        for sid in get_commander_home_style_list(level):
            if sid == style_id:
                return True
    except Exception:
        pass
    return style_id == 1


def _is_commander_home_style_known(style_id: int) -> bool:
    if style_id == 1:
        return True
    try:
        from src.orm.config_entry import get_config_entry
        entry = get_config_entry("ShareCfg/commander_home_style.json", str(style_id))
        return entry is not None
    except Exception:
        return False
