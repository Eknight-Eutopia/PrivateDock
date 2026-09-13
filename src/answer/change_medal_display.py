import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

MAX_MEDAL_DISPLAY_ENTRIES = 5


def _validate_medal_display_list(medal_ids: list[int]) -> bool:
    if not medal_ids:
        return True
    seen = set()
    for mid in medal_ids:
        if mid == 0:
            return False
        if mid in seen:
            return False
        seen.add(mid)
    return True


def handle_change_medal_display(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_17401()
    payload.ParseFromString(buffer)
    response = protobuf.SC_17402(result=0)

    if payload.fixed_const != 1:
        response.result = 1
        asyncio.create_task(client.send_message(17402, response))
        return 0, 17402, None

    medal_ids = list(payload.medal_id)
    if len(medal_ids) > MAX_MEDAL_DISPLAY_ENTRIES:
        response.result = 1
        asyncio.create_task(client.send_message(17402, response))
        return 0, 17402, None

    if not _validate_medal_display_list(medal_ids):
        response.result = 1
        asyncio.create_task(client.send_message(17402, response))
        return 0, 17402, None

    from src.orm.commander_medal_display import set_commander_medal_display
    try:
        set_commander_medal_display(client.commander.commander_id, medal_ids)
    except Exception:
        response.result = 1

    asyncio.create_task(client.send_message(17402, response))
    return 0, 17402, None
