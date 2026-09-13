import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

RESPONSE_PACKET_ID = 17602


def handle_equip_code_share_list_request(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_17601()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, RESPONSE_PACKET_ID, e

    _ = payload.shipgroup
    response = protobuf.SC_17602(
        result=0,
        infos=[],
        recent_infos=[],
    )
    asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, response))
    return 0, RESPONSE_PACKET_ID, None
