import asyncio
import time
from typing import Optional

from src.connection.client import Client
from src.consts.drop_types import DROP_TYPE_ITEM
from src.orm.reflux_state import get_or_create_reflux_state, save_reflux_state
from .reflux_helpers import (
    load_return_sign_templates,
    select_level_index,
    build_award_drops,
    is_reflux_expired,
    is_same_day,
    ensure_commander_loaded,
)

PACKET_ID = 33042


def _apply_drop(client, drop_type, drop_id, drop_count):
    c = client.commander
    if drop_type == 1:
        c.add_resource(drop_id, drop_count)
    elif drop_type == 2:
        c.add_item(drop_id, drop_count)
    elif drop_type == 4:
        for _ in range(drop_count):
            c.add_ship(drop_id)
    elif drop_type == 7:
        for _ in range(drop_count):
            c.give_skin(drop_id)
    elif drop_type == 8:
        pass


def handle_reflux_sign(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1, "award_list": []}))
        return 0, PACKET_ID, None

    now_unix = int(time.time())

    sign_templates, sign_ids = load_return_sign_templates()
    if not sign_ids:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1, "award_list": []}))
        return 0, PACKET_ID, None

    state = get_or_create_reflux_state(client.commander.commander_id)

    response = {"result": 1, "award_list": []}
    if state.active != 1:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    if is_reflux_expired(state.return_time, len(sign_ids), now_unix):
        state.active = 0
        save_reflux_state(state)
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    if state.sign_cnt >= len(sign_ids):
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    if is_same_day(state.sign_last_time, now_unix):
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    err = ensure_commander_loaded(client, "Reflux")
    if err is not None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, err

    next_id = state.sign_cnt + 1
    config = sign_templates.get(next_id)
    if config is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    level_ranges = config.get("level", [])
    level_index, err = select_level_index(state.return_lv, level_ranges)
    if err is not None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, err

    award_display = config.get("award_display", [])
    if level_index < len(award_display):
        display = award_display[level_index]
    else:
        display = []
    drops = build_award_drops(display)

    for drop in drops:
        _apply_drop(client, drop["type"], drop["id"], drop["number"])

    state.sign_cnt += 1
    state.sign_last_time = now_unix
    save_reflux_state(state)

    response = {"result": 0, "award_list": drops}
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
