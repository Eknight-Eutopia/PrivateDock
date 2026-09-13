import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_update_ship_like(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    import json
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    ship_group_id = payload.get("ship_group_id", 0)
    like_error = None
    try:
        like_error = client.commander.like(ship_group_id)
    except Exception as e:
        like_error = e

    result = 1 if like_error else 0
    asyncio.create_task(client.send_message(17108, protobuf.SC_17108(result=result)))
    if result != 0:
        return 0, 17108, None

    from .collection_sync import send_collection_ship_group_update
    try:
        send_collection_ship_group_update(client, ship_group_id)
    except Exception:
        pass
    return 0, 17108, None
