import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def _send_15003(client, result=1, drop_list=None):
    resp = protobuf.SC_15003(result=result)
    if drop_list:
        for d in drop_list:
            resp.drop_list.append(protobuf.DROPINFO(type=d["type"], id=d["id"], number=d["number"]))
    asyncio.create_task(client.send_message(15003, resp))


def handle_use_item(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_15002.FromString(buffer)

    item_id = payload.id
    count = payload.count
    arg = list(payload.arg) if payload.arg else []

    if count == 0:
        _send_15003(client)
        return 0, 15003, None

    if client.commander is not None:
        items_map = getattr(client.commander, "commander_items_map", None)
        misc_map = getattr(client.commander, "misc_items_map", None)
        if items_map is None and misc_map is None:
            try:
                client.commander.load()
            except Exception as e:
                _send_15003(client)
                return 0, 15003, e

    from src.answer.item_usage import use_item as _use_item_impl
    try:
        outcome = _use_item_impl(client, item_id, count, arg)
        if outcome:
            _send_15003(client, outcome.get("result", 1), outcome.get("drop_list", []))
        else:
            _send_15003(client)
    except Exception as e:
        _send_15003(client)
        return 0, 15003, e

    return 0, 15003, None
