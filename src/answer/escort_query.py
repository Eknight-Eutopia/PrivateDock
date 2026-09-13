import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.misc.escort import get_escort_config, load_escort_state


PACKET_ID = 13302


def handle_escort_query(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_13301()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    _ = get_escort_config()
    escort_info = []
    if client.commander is not None:
        try:
            escort_info = load_escort_state(client.commander.account_id)
        except Exception:
            pass

    response = protobuf.SC_13302()
    response.drop_list.extend([])
    response.escort_info.extend(escort_info)
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
