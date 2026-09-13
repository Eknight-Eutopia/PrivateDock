import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

from .helpers import set_commander_common_flag


def handle_month_shop_flag(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_16203()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 16204, e

    response = protobuf.SC_16204()
    response.ret = 0

    try:
        set_commander_common_flag(client.commander.commander_id, payload.flag)
    except Exception:
        response.ret = 1

    asyncio.create_task(client.send_message(16204, response))
    return 0, 16204, None
