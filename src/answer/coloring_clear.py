import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_coloring_clear(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from .coloring_helpers import (
        COLORING_RESULT_FAILURE,
        COLORING_RESULT_SUCCESS,
        load_coloring_activity_pages,
        load_coloring_template,
        get_or_create_coloring_state,
        coloring_clear_page,
    )

    PACKET_ID = 26007
    response = {"result": COLORING_RESULT_FAILURE}

    try:
        payload = protobuf.CS_26006()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    act_id = payload.act_id
    page_id = payload.id

    pages = load_coloring_activity_pages(act_id)
    page_exists = any(p["page_id"] == page_id for p in pages)
    if not page_exists:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    template = load_coloring_template(page_id)
    if template is None or template.get("blank", 0) != 1:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    try:
        state = get_or_create_coloring_state(client.commander.commander_id, act_id)
    except Exception as e:
        return 0, PACKET_ID, e

    coloring_clear_page(state, page_id)
    try:
        from src.orm.commander_coloring_state import save_commander_coloring_state
        save_commander_coloring_state(state)
    except Exception as e:
        return 0, PACKET_ID, e

    response["result"] = COLORING_RESULT_SUCCESS
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
