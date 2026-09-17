import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_set_favorite_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    ship_id = 0
    flag = 0
    try:
        payload = protobuf.CS_12040()
        payload.ParseFromString(buffer)
        ship_id = payload.ship_id
        flag = payload.flag
    except Exception:
        try:
            import json
            data = json.loads(buffer.decode("utf-8", errors="replace"))
            ship_id = data.get("ship_id", 0)
            flag = data.get("flag", 0)
        except Exception as e:
            asyncio.create_task(client.send_message(12041, protobuf.SC_12041(result=1)))
            return 0, 12041, e

    if client.commander is None:
        asyncio.create_task(client.send_message(12041, protobuf.SC_12041(result=1)))
        return 0, 12041, None

    owned_map = getattr(client.commander, "owned_ships_map", {}) or {}
    ship = owned_map.get(ship_id)
    if ship is None:
        asyncio.create_task(client.send_message(12041, protobuf.SC_12041(result=1)))
        return 0, 12041, None

    result = 0
    from src.orm.owned_ship import set_ship_favorite
    try:
        set_ship_favorite(ship, flag)
    except Exception:
        result = 1

    asyncio.create_task(client.send_message(12041, protobuf.SC_12041(result=result)))
    return 0, 12041, None
