import asyncio
from typing import Optional

from src.connection.client import Client
from src.orm.remaster import get_or_create_remaster_state, set_remaster_active_chapter_sync
from src.protobuf import protobuf

RESPONSE_PACKET_ID = 13502


def handle_remaster_set_active_chapter(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, protobuf.SC_13502(result=1)))
        return 0, RESPONSE_PACKET_ID, None

    try:
        payload = protobuf.CS_13501()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, RESPONSE_PACKET_ID, e

    commander_id = client.commander.commander_id
    state = get_or_create_remaster_state(commander_id)
    state.active_chapter_id = payload.active_id

    set_remaster_active_chapter_sync(commander_id, payload.active_id)

    response = protobuf.SC_13502(result=0)
    asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, response))
    return 0, RESPONSE_PACKET_ID, None
