import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_coloring_cell(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from .coloring_helpers import (
        COLORING_RESULT_FAILURE,
        COLORING_RESULT_SUCCESS,
        load_coloring_activity_pages,
        load_coloring_template,
        build_coloring_cell_template_lookup,
        coloring_cell_key,
        get_or_create_coloring_state,
        coloring_set_cell,
    )

    PACKET_ID = 26005
    response = {"result": COLORING_RESULT_FAILURE}

    try:
        payload = protobuf.CS_26004()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    act_id = payload.act_id
    page_id = payload.id
    cell_list = payload.cell_list

    pages = load_coloring_activity_pages(act_id)
    if not pages:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    page_exists = any(p["page_id"] == page_id for p in pages)
    if not page_exists:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    template = load_coloring_template(page_id)
    if template is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    cell_template_lookup = build_coloring_cell_template_lookup(template)
    if not cell_template_lookup:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    item_consume = {}
    applied_cells = {}

    for cell in cell_list:
        key = coloring_cell_key(cell.row, cell.column)
        tpl_cell = cell_template_lookup.get(key)
        if tpl_cell is None:
            asyncio.create_task(client.send_message(PACKET_ID, response))
            return 0, PACKET_ID, None
        color = cell.color
        color_id_list = template.get("color_id_list", [])
        if color > len(color_id_list):
            asyncio.create_task(client.send_message(PACKET_ID, response))
            return 0, PACKET_ID, None
        if template.get("blank", 0) == 0:
            if color == 0 or tpl_cell.get("required", 0) == 0 or color != tpl_cell.get("required", 0):
                asyncio.create_task(client.send_message(PACKET_ID, response))
                return 0, PACKET_ID, None
        applied_cells[key] = cell

    if template.get("blank", 0) == 0:
        for cell in applied_cells.values():
            color_id_list = template.get("color_id_list", [])
            item_id = color_id_list[cell.color - 1]
            if item_id == 0:
                asyncio.create_task(client.send_message(PACKET_ID, response))
                return 0, PACKET_ID, None
            item_consume[item_id] = item_consume.get(item_id, 0) + 1

    try:
        state = get_or_create_coloring_state(client.commander.commander_id, act_id)
    except Exception as e:
        return 0, PACKET_ID, e

    try:
        for item_id, count in item_consume.items():
            if not client.commander.has_enough_item(item_id, count):
                asyncio.create_task(client.send_message(PACKET_ID, response))
                return 0, PACKET_ID, None
            client.commander.consume_item(item_id, count)

        for cell in applied_cells.values():
            coloring_set_cell(state, page_id, cell.row, cell.column, cell.color)

        from src.orm.commander_coloring_state import save_commander_coloring_state
        save_commander_coloring_state(state)
    except Exception as e:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, e

    try:
        client.commander.load()
    except Exception as e:
        return 0, PACKET_ID, e

    response["result"] = COLORING_RESULT_SUCCESS
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
