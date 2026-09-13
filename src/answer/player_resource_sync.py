import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def build_resource_snapshot(resources) -> list[dict]:
    if not resources:
        return []
    return [{"type": r.id, "num": r.count} for r in resources]


def send_player_resource_sync(client: Client) -> tuple[int, int, Optional[Exception]]:
    if client is None or client.commander is None:
        return 0, 11004, Exception("missing commander")
    res_map = getattr(client.commander, "owned_resources_map", {}) or {}
    response = protobuf.SC_11004()
    for rid, v in res_map.items():
        response.resource_list.append(
            protobuf.RESOURCE(type=int(rid), num=int(v.get("amount", 0)))
        )
    asyncio.create_task(client.send_message(11004, response))
    return 0, 11004, None
