import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_fleet_commit(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12102()
    payload.ParseFromString(buffer)
    response = protobuf.SC_12103(result=0)

    fleet_id = payload.id
    ship_ids = list(payload.ship_list)

    from src.orm.fleet import get_fleet_by_game_id, create_fleet, update_fleet_ships

    fleet = get_fleet_by_game_id(client.commander.commander_id, fleet_id)
    if fleet is None:
        try:
            fleet = create_fleet(client.commander.commander_id, "", fleet_id)
        except Exception as e:
            response.result = 1
    if response.result == 0:
        try:
            update_fleet_ships(fleet.id, ship_ids)
        except Exception as e:
            response.result = 1

    asyncio.create_task(client.send_message(12103, response))
    if response.result != 0:
        return 0, 12103, None

    from .fleet_sync_push import push_fleet_sync
    try:
        push_fleet_sync(client, fleet)
    except Exception as e:
        return 0, 12106, e
    return 0, 12103, None
