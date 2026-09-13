import asyncio
from typing import Optional

from src.connection.client import Client
from src.logger.logger import LOG_LEVEL_ERROR, log_event
from src.protobuf import protobuf
from src.region.region import current as get_region
from src.misc import resolve_region_version
from src.config.regions import GAME_PLATFORM_URL



def _parse_version_parts(version: str) -> list[int]:
    if not version:
        raise ValueError("empty version")
    segments = version.split(".")
    if len(segments) < 3 or len(segments) > 4:
        raise ValueError(f"invalid version format {version!r}")
    parts = []
    for seg in segments:
        parts.append(int(seg))
    while len(parts) < 4:
        parts.append(0)
    return parts


def handle_version_check(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    response_id = 10997
    try:
        payload = protobuf.CS_10996()
        payload.ParseFromString(buffer)

        region = get_region()
        version_string = resolve_region_version(region)
        version_parts = _parse_version_parts(version_string)

        platform = payload.platform if payload.HasField("platform") else ""
        url_dict = GAME_PLATFORM_URL.get(region, {})
        url = url_dict.get(platform)
        if url is None:
            from .update_packet import PLATFORM_MAP
            resolved = PLATFORM_MAP.get(platform, "Unknown")
            return 0, response_id, ValueError(f"unknown platform '{resolved}' (id='{platform}')")

        from src.config.regions import REGION_GATEWAYS
        response = protobuf.SC_10997(
            version1=version_parts[0],
            version2=version_parts[1],
            version3=version_parts[2],
            version4=version_parts[3],
            gateway_ip=REGION_GATEWAYS.get(region, ""),
            gateway_port=80,
            url=url,
        )
        asyncio.create_task(client.send_message(response_id, response))
    except Exception as e:
        log_event("Answer", "version_check", f"Error: {e}", LOG_LEVEL_ERROR)
    return 0, response_id, None
