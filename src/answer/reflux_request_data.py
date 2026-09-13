import asyncio
import time
from typing import Optional

from src.connection.client import Client
from src.orm.reflux_state import get_or_create_reflux_state, save_reflux_state
from src.orm.item import get_commander_item_count
from .reflux_helpers import (
    load_return_sign_templates,
    load_return_pt_templates,
    load_reflux_eligibility_config,
    is_reflux_expired,
    is_reflux_eligible,
    ensure_commander_loaded,
)

PACKET_ID = 33040


def _inactive_response() -> dict:
    return {"active": 0, "return_lv": 0, "return_time": 0, "ship_number": 0, "last_offline_time": 0, "pt": 0, "sign_cnt": 0, "sign_last_time": 0, "pt_stage": 0}


def handle_reflux_request_data(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, _inactive_response()))
        return 0, PACKET_ID, None

    now_unix = int(time.time())
    now_time = time.time()

    sign_templates, sign_ids = load_return_sign_templates()
    if not sign_ids:
        asyncio.create_task(client.send_message(PACKET_ID, _inactive_response()))
        return 0, PACKET_ID, None

    _, _, pt_item_id = load_return_pt_templates()
    state = get_or_create_reflux_state(client.commander.commander_id)

    if state.active == 1 and is_reflux_expired(state.return_time, len(sign_ids), now_unix):
        state.active = 0
        save_reflux_state(state)

    if state.active == 0:
        cfg, ok = load_reflux_eligibility_config()
        if ok and is_reflux_eligible(client, cfg, now_time):
            err = ensure_commander_loaded(client, "Reflux")
            if err is not None:
                asyncio.create_task(client.send_message(PACKET_ID, _inactive_response()))
                return 0, PACKET_ID, err
            state.active = 1
            state.return_lv = client.commander.level
            state.return_time = now_unix
            state.ship_number = len(getattr(client.commander, "owned_ships_map", {}) or {})
            state.last_offline_time = int(client.previous_login_at) if client.previous_login_at else 0
            state.pt = 0
            state.sign_cnt = 0
            state.sign_last_time = 0
            state.pt_stage = 0

    if state.active == 1 and pt_item_id != 0:
        pt_count = get_commander_item_count(client.commander.commander_id, pt_item_id)
        state.pt = pt_count

    save_reflux_state(state)

    if state.active == 1:
        response = {
            "active": 1,
            "return_lv": state.return_lv,
            "return_time": state.return_time,
            "ship_number": state.ship_number,
            "last_offline_time": state.last_offline_time,
            "pt": state.pt,
            "sign_cnt": state.sign_cnt,
            "sign_last_time": state.sign_last_time,
            "pt_stage": state.pt_stage,
        }
    else:
        response = _inactive_response()

    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
