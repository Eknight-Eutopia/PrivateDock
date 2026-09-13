import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_shop_refresh(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 16004

    response = protobuf.SC_16004(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
