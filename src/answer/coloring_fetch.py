import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_coloring_fetch(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from .coloring_helpers import (
        load_coloring_activity_pages,
        load_coloring_template,
        get_or_create_coloring_state,
        coloring_current_page_id,
        coloring_build_cell_list_for_page,
        coloring_build_color_list,
        coloring_build_award_list,
    )

    PACKET_ID = 26001

    try:
        payload = protobuf.CS_26008()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    if getattr(client.commander, "owned_ships_map", None) is None:
        try:
            client.commander.load()
        except Exception as e:
            return 0, PACKET_ID, e

    act_id = payload.act_id

    try:
        pages = load_coloring_activity_pages(act_id)
    except Exception as e:
        return 0, PACKET_ID, e

    try:
        state = get_or_create_coloring_state(client.commander.commander_id, act_id)
    except Exception as e:
        return 0, PACKET_ID, e

    color_item_ids = set()
    for page in pages:
        template = load_coloring_template(page["page_id"])
        if template is None:
            continue
        for item_id in template.get("color_id_list", []):
            if item_id == 0:
                continue
            color_item_ids.add(item_id)

    counts = {}
    for item_id in color_item_ids:
        counts[item_id] = client.commander.get_item_count(item_id)

    current_page_id = coloring_current_page_id(state, pages)
    response = {
        "id": current_page_id,
        "cell_list": coloring_build_cell_list_for_page(state, current_page_id),
        "color_list": coloring_build_color_list(counts),
        "award_list": coloring_build_award_list(state),
        "start_time": state.get("start_time", 0),
    }
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
