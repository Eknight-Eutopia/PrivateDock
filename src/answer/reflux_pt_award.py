import asyncio
import time
from typing import Optional

from src.connection.client import Client
from src.orm.reflux_state import get_or_create_reflux_state, save_reflux_state
from src.orm.item import get_commander_item_count
from .reflux_helpers import (
    load_return_sign_templates,
    load_return_pt_templates,
    select_level_index,
    build_award_drops,
    is_reflux_expired,
    ensure_commander_loaded,
)

PACKET_ID = 33046


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
    elif drop_type in (14, 15, 31):
        from src.orm.commander_attire import grant_commander_attire_drop_sync
        grant_commander_attire_drop_sync(c.commander_id, drop_type, drop_id, drop_count)


def handle_reflux_pt_award(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1, "award_list": []}))
        return 0, PACKET_ID, None

    now_unix = int(time.time())

    pt_templates, _, pt_item_id = load_return_pt_templates()
    if not pt_templates:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1, "award_list": []}))
        return 0, PACKET_ID, None

    _, sign_ids = load_return_sign_templates()

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

    err = ensure_commander_loaded(client, "Reflux")
    if err is not None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, err

    if pt_item_id != 0:
        pt_count = get_commander_item_count(client.commander.commander_id, pt_item_id)
        state.pt = pt_count
        save_reflux_state(state)

    next_stage = state.pt_stage + 1
    config = pt_templates.get(next_stage)
    if config is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    pt_require = config.get("pt_require", 0)
    if state.pt < pt_require:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    level_ranges = config.get("level", [])
    level_index, err = select_level_index(state.return_lv, level_ranges)
    if err is not None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, err

    award_display = config.get("award_display", [])
    if level_index < len(award_display):
        display = [award_display[level_index]]
    else:
        display = []
    drops = build_award_drops(display)

    for drop in drops:
        _apply_drop(client, drop["type"], drop["id"], drop["number"])

    state.pt_stage += 1
    save_reflux_state(state)

    response = {"result": 0, "award_list": drops}
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
