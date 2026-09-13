import asyncio
from typing import Optional

from src.config.config import current as get_config
from src.connection.client import Client
from src.protobuf import protobuf


def handle_gateway_pack_info(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    packet_id = 10701
    payload = protobuf.CS_10700()
    payload.ParseFromString(buffer)

    from .update_packet import _update_versions, PLATFORM_MAP
    from src.misc import get_game_hashes
    _update_versions(get_game_hashes)

    from src.region.region import current as get_region
    from src.config.regions import GAME_PLATFORM_URL, MONDAY_0CLOCK_TIMESTAMPS
    import time

    region = get_region()
    platform = payload.platform if payload.HasField("platform") else ""
    resolved = PLATFORM_MAP.get(platform, "Unknown")
    url_dict = GAME_PLATFORM_URL.get(region, {})
    url = url_dict.get(platform)
    if url is None:
        return 0, packet_id, ValueError(f"unknown platform '{resolved}' (id='{platform}')")

    from .update_packet import _versions as versions
    from .server_status_cache import get_server_status_cache
    from .servers import build_gateway_addr_list

    cfg = get_config()
    statuses = get_server_status_cache(cfg.servers)
    addr_list = build_gateway_addr_list(cfg.servers, statuses)

    response = protobuf.SC_10701(
        url=url,
        version=versions,
        timestamp=int(time.time()),
        monday_0oclock_timestamp=MONDAY_0CLOCK_TIMESTAMPS.get(region, 0),
    )
    response.addr_list.extend(addr_list)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
