import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

PACKET_ID = 17110


def handle_report_ship_evaluation_proto(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_17109()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    response = protobuf.SC_17110(result=0)
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
