import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

from .helpers import (
    apply_lesson_exp,
    calc_granted_lesson_exp,
    consume_commander_quick_finish,
    create_commander_skill_class,
    delete_commander_skill_class,
    get_commander_daily_quick_finish_used,
    get_commander_skill_class_by_room,
    get_commander_skill_learn_time_allowance,
    get_or_create_commander_ship_skill,
    lesson_exp_from_usage_arg,
    list_config_entries,
    load_lesson_item_config,
    load_ship_skill_by_pos,
    load_skill_template,
    save_commander_ship_skill,
    LESSON_ITEM_TYPE,
    LESSON_ITEM_USAGE,
)

LESSON_RESULT_OK = 0
LESSON_RESULT_FAILED = 1

LESSON_QUICK_FINISH_RESULT_OK = 0
LESSON_QUICK_FINISH_RESULT_INVALID_ROOM = 1
LESSON_QUICK_FINISH_RESULT_SESSION_NOT_FOUND = 2
LESSON_QUICK_FINISH_RESULT_ALLOWANCE_EXCEEDED = 3
LESSON_QUICK_FINISH_RESULT_INVALID_STATE = 4

SKILL_CANCEL_TYPE_AUTO = 0
SKILL_CANCEL_TYPE_MANUAL = 1


async def handle_start_learn_tactics(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_22201()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 22202, e

    response = protobuf.SC_22202()
    response.result = LESSON_RESULT_FAILED

    room_id = payload.room_id
    ship_id = payload.ship_id
    skill_pos = payload.skill_pos
    item_id = payload.item_id

    if room_id == 0 or ship_id == 0 or skill_pos == 0 or item_id == 0:
        await client.send_message(22202, response)
        return 0, 22202, None

    if getattr(client.commander, "owned_ships_map", None) is None or getattr(client.commander, "commander_items_map", None) is None:
        if hasattr(client.commander, "load"):
            client.commander.load()

    academy_entries = await list_config_entries("ShareCfg/navalacademy_data_template.json")
    if room_id > len(academy_entries):
        await client.send_message(22202, response)
        return 0, 22202, None

    owned_ships_map = getattr(client.commander, "owned_ships_map", {}) or {}
    owned_ship = owned_ships_map.get(ship_id)
    if owned_ship is None:
        await client.send_message(22202, response)
        return 0, 22202, None

    ship_template_id = owned_ship.get("ship_id", owned_ship.get("id", 0))
    if hasattr(owned_ship, "ship_id"):
        ship_template_id = owned_ship.ship_id

    skill_id = await load_ship_skill_by_pos(ship_template_id, skill_pos)
    if skill_id is None:
        await client.send_message(22202, response)
        return 0, 22202, None

    skill_config = await load_skill_template(skill_id)
    if skill_config is None:
        await client.send_message(22202, response)
        return 0, 22202, None

    lesson_config = await load_lesson_item_config(item_id)
    if lesson_config is None:
        await client.send_message(22202, response)
        return 0, 22202, None

    item_type, usage, usage_arg = lesson_config
    if item_type != LESSON_ITEM_TYPE or usage != LESSON_ITEM_USAGE:
        await client.send_message(22202, response)
        return 0, 22202, None

    duration, lesson_exp = lesson_exp_from_usage_arg(usage_arg, skill_config.get("type", 0))
    if duration == 0 or lesson_exp == 0:
        await client.send_message(22202, response)
        return 0, 22202, None

    now_unix = int(time.time())
    finish_time = now_unix + duration

    commander_id = client.commander.commander_id

    ship_skill = await get_or_create_commander_ship_skill(commander_id, ship_id, skill_pos, skill_id)
    if ship_skill is None:
        await client.send_message(22202, response)
        return 0, 22202, None

    if ship_skill.get("level", 0) >= skill_config.get("max_level", 10):
        await client.send_message(22202, response)
        return 0, 22202, None

    err = await create_commander_skill_class(commander_id, room_id, ship_id, skill_pos, skill_id, now_unix, finish_time, lesson_exp)
    if err is not None:
        err_str = str(err)
        if "23505" in err_str or "duplicate" in err_str.lower() or "unique" in err_str.lower():
            await client.send_message(22202, response)
            return 0, 22202, None
        return 0, 22202, err

    if hasattr(client.commander, "consume_item"):
        client.commander.consume_item(item_id, 1)

    response.result = LESSON_RESULT_OK
    class_info = protobuf.SKILL_CLASS()
    class_info.room_id = room_id
    class_info.ship_id = ship_id
    class_info.start_time = now_unix
    class_info.finish_time = finish_time
    class_info.skill_pos = skill_pos
    class_info.exp = lesson_exp
    response.class_info.CopyFrom(class_info)

    # Server-authoritative task progress: "Conduct Tactical Training X times"
    # (sub_type 71) — one started lesson per successful request.
    try:
        from src.answer.task_handlers import schedule_emit
        schedule_emit(client, 71, 0, 1)
    except Exception:
        pass

    await client.send_message(22202, response)
    return 0, 22202, None


async def handle_quick_finish_learn_tactics(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_22014()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 22015, e

    response = protobuf.SC_22015()
    response.result = LESSON_QUICK_FINISH_RESULT_INVALID_ROOM

    room_id = payload.roomid
    if room_id == 0:
        await client.send_message(22015, response)
        return 0, 22015, None

    if getattr(client.commander, "owned_ships_map", None) is None:
        if hasattr(client.commander, "load"):
            client.commander.load()

    now_unix = int(time.time())
    commander_id = client.commander.commander_id

    lesson = await get_commander_skill_class_by_room(commander_id, room_id)
    if lesson is None:
        response.result = LESSON_QUICK_FINISH_RESULT_SESSION_NOT_FOUND
        await client.send_message(22015, response)
        return 0, 22015, None

    allowance = await get_commander_skill_learn_time_allowance(commander_id, now_unix)
    if allowance == 0:
        response.result = LESSON_QUICK_FINISH_RESULT_ALLOWANCE_EXCEEDED
        await client.send_message(22015, response)
        return 0, 22015, None

    used = await get_commander_daily_quick_finish_used(commander_id, now_unix)
    if used >= allowance:
        response.result = LESSON_QUICK_FINISH_RESULT_ALLOWANCE_EXCEEDED
        await client.send_message(22015, response)
        return 0, 22015, None

    skill_config = await load_skill_template(lesson["skill_id"])
    if skill_config is None:
        response.result = LESSON_QUICK_FINISH_RESULT_INVALID_STATE
        await client.send_message(22015, response)
        return 0, 22015, None

    ship_skill = await get_or_create_commander_ship_skill(
        commander_id, lesson["ship_id"], lesson["skill_pos"], lesson["skill_id"]
    )
    if ship_skill is None:
        response.result = LESSON_QUICK_FINISH_RESULT_INVALID_STATE
        await client.send_message(22015, response)
        return 0, 22015, None

    grant = apply_lesson_exp(ship_skill, lesson["exp"], skill_config.get("max_level", 10))
    if grant > 0:
        err = await save_commander_ship_skill(ship_skill)
        if err is not None:
            response.result = LESSON_QUICK_FINISH_RESULT_INVALID_STATE
            await client.send_message(22015, response)
            return 0, 22015, None

    err = await delete_commander_skill_class(commander_id, room_id)
    if err is not None:
        response.result = LESSON_QUICK_FINISH_RESULT_SESSION_NOT_FOUND
        await client.send_message(22015, response)
        return 0, 22015, None

    err = await consume_commander_quick_finish(commander_id, allowance, now_unix)
    if err is not None:
        response.result = LESSON_QUICK_FINISH_RESULT_ALLOWANCE_EXCEEDED
        await client.send_message(22015, response)
        return 0, 22015, None

    response.result = LESSON_QUICK_FINISH_RESULT_OK
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 71, 0, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    await client.send_message(22015, response)
    return 0, 22015, None


async def handle_cancel_learn_tactics(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_22203()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 22204, e

    response = protobuf.SC_22204()
    response.result = LESSON_RESULT_FAILED

    room_id = payload.room_id
    cancel_type = payload.type

    if room_id == 0:
        await client.send_message(22204, response)
        return 0, 22204, None

    if cancel_type != SKILL_CANCEL_TYPE_AUTO and cancel_type != SKILL_CANCEL_TYPE_MANUAL:
        await client.send_message(22204, response)
        return 0, 22204, None

    commander_id = client.commander.commander_id
    lesson = await get_commander_skill_class_by_room(commander_id, room_id)
    if lesson is None:
        await client.send_message(22204, response)
        return 0, 22204, None

    skill_config = await load_skill_template(lesson["skill_id"])
    if skill_config is None:
        await client.send_message(22204, response)
        return 0, 22204, None

    ship_skill = await get_or_create_commander_ship_skill(
        commander_id, lesson["ship_id"], lesson["skill_pos"], lesson["skill_id"]
    )
    if ship_skill is None:
        await client.send_message(22204, response)
        return 0, 22204, None

    now_unix = int(time.time())
    candidate_exp = calc_granted_lesson_exp(now_unix, lesson["start_time"], lesson["finish_time"], lesson["exp"])
    granted_exp = apply_lesson_exp(ship_skill, candidate_exp, skill_config.get("max_level", 10))

    if granted_exp > 0:
        err = await save_commander_ship_skill(ship_skill)
        if err is not None:
            return 0, 22204, err

    err = await delete_commander_skill_class(commander_id, room_id)
    if err is not None:
        await client.send_message(22204, response)
        return 0, 22204, None

    response.result = LESSON_RESULT_OK
    response.exp = granted_exp
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 71, 0, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    await client.send_message(22204, response)
    return 0, 22204, None
