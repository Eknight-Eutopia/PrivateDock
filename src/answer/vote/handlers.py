import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_fetch_vote_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_17203()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 17204, e

    response = protobuf.SC_17204()
    asyncio.create_task(client.send_message(17204, response))
    return 0, 17204, None


def handle_fetch_vote_ticket_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_17201()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 17202, e

    response = protobuf.SC_17202()
    response.daily_vote = 0
    response.love_vote = 0
    response.daily_ship_list.extend([])

    asyncio.create_task(client.send_message(17202, response))
    return 0, 17202, None
