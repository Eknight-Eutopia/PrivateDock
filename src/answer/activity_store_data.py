import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_activity_store_data(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 26161
    payload = protobuf.CS_26160()
    payload.ParseFromString(buffer)

    response = protobuf.SC_26161(result=1)

    if client.commander is None or payload.act_id == 0:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    act_id = payload.act_id
    from .activity_templates import load_activity_template
    try:
        template = load_activity_template(act_id)
    except Exception:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    from .activity_constants import parse_activity_time_window
    import time
    _, _, active, err = parse_activity_time_window(template.time, int(time.time()))
    if err is not None or not active:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    from src.orm.activity_store import upsert_activity_store_state
    try:
        upsert_activity_store_state({
            "commander_id": client.commander.commander_id,
            "activity_id": act_id,
            "data1": payload.int_value,
            "str_data1": payload.str_value if payload.HasField("str_value") else "",
        })
    except Exception:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response.result = 0
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
