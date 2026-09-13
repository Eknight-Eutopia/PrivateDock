import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

PACKET_ID = 13108


def handle_remaster_chapter_info(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_13108(result=0)))
    return 0, PACKET_ID, None
