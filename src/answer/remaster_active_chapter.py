import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.orm.remaster import get_or_create_remaster_state, set_remaster_active_chapter_sync

PACKET_ID = 24610


def handle_remaster_request_active_chapter(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1, "chapter_list": []}))
        return 0, PACKET_ID, None

    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception:
        payload = {}

    state = get_or_create_remaster_state(client.commander.commander_id)
    active_id = payload.get("active_id", 0)
    state.active_chapter_id = active_id

    set_remaster_active_chapter_sync(client.commander.commander_id, active_id)

    response = {"result": 0}
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
