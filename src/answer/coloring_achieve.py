import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_coloring_achieve(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from .coloring_helpers import (
        COLORING_RESULT_FAILURE,
        COLORING_RESULT_SUCCESS,
        load_coloring_activity_pages,
        load_coloring_template,
        get_or_create_coloring_state,
        coloring_is_page_claimed,
        coloring_get_page_fills,
        coloring_is_page_complete,
        coloring_resolve_claim_drops,
        coloring_add_claim,
        coloring_apply_drops,
    )

    PACKET_ID = 26003
    response = {"result": COLORING_RESULT_FAILURE, "drop_list": []}

    try:
        payload = protobuf.CS_26002()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    act_id = payload.act_id
    page_id = payload.id

    pages = load_coloring_activity_pages(act_id)
    if not pages:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    page = None
    for p in pages:
        if p["page_id"] == page_id:
            page = p
            break
    if page is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    template = load_coloring_template(page_id)
    if template is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    try:
        state = get_or_create_coloring_state(client.commander.commander_id, act_id)
    except Exception as e:
        return 0, PACKET_ID, e

    if coloring_is_page_claimed(state, page_id):
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    fills = coloring_get_page_fills(state, page_id)
    if not coloring_is_page_complete(template, fills):
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    drops = coloring_resolve_claim_drops(page.get("reward_spec", []))
    try:
        coloring_add_claim(state, page_id, drops)
        from src.orm.commander_coloring_state import save_commander_coloring_state
        save_commander_coloring_state(state)
        coloring_apply_drops(client.commander.commander_id, drops)
    except Exception as e:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, e

    try:
        client.commander.load()
    except Exception as e:
        return 0, PACKET_ID, e

    response["result"] = COLORING_RESULT_SUCCESS
    response["drop_list"] = drops
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
