import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_fleet_rename(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12104()
    payload.ParseFromString(buffer)
    response = protobuf.SC_12105(result=0)

    fleet_id = payload.id
    name = payload.name
    fleets_map = getattr(client.commander, "fleets_map", {}) or {}

    fleet = fleets_map.get(fleet_id)
    if fleet is None:
        response.result = 1
    else:
        from src.orm.fleet import rename_fleet
        try:
            rename_fleet(fleet, name)
        except Exception:
            response.result = 2

    asyncio.create_task(client.send_message(12105, response))
    if response.result != 0:
        return 0, 12105, None

    from .fleet_sync_push import push_fleet_sync
    try:
        push_fleet_sync(client, fleet)
    except Exception as e:
        return 0, 12106, e
    return 0, 12105, None
