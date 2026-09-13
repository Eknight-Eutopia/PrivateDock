import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

from .helpers import current_region, REGION_GATEWAYS, REGION_PROXIES


def handle_build_server_interconnection_response(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    region = current_region()
    response = protobuf.SC_10803()
    response.gateway_ip = REGION_GATEWAYS.get(region, "")
    response.gateway_port = 80
    response.proxy_ip = REGION_PROXIES.get(region, "")
    response.proxy_port = 20000

    asyncio.create_task(client.send_message(10803, response))
    return 0, 10803, None
