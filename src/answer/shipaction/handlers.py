import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

from .helpers import SHIP_ACTION_VALIDATE_RESULT_OK, SHIP_ACTION_VALIDATE_RESULT_NOT_FOUND


def handle_ship_action_list(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        data = protobuf.CS_12029()
        data.ParseFromString(buffer)
    except Exception as e:
        return 0, 12030, e

    response = protobuf.SC_12030()
    response.result = 0
    response.ship_list.extend([])

    asyncio.create_task(client.send_message(12030, response))
    return 0, 12030, None


def handle_ship_action_validate(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        data = protobuf.CS_12020()
        data.ParseFromString(buffer)
    except Exception as e:
        return 0, 12021, e

    response = protobuf.SC_12021()
    response.result = SHIP_ACTION_VALIDATE_RESULT_OK

    ship = client.commander.owned_ships_map.get(data.ship_id)
    ok = ship is not None
    if not ok:
        response.result = SHIP_ACTION_VALIDATE_RESULT_NOT_FOUND

    asyncio.create_task(client.send_message(12021, response))

    if ok:
        push = protobuf.SC_12019()
        push.intimacy = ship.intimacy
        asyncio.create_task(client.send_message(12019, push))

    return 0, 12021, None
