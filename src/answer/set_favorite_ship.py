import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_set_favorite_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    import json
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    ship_id = payload.get("ship_id", 0)
    flag = payload.get("flag", 0)
    ships_map = getattr(client.commander, "ships_map", {}) or {}

    ship = ships_map.get(ship_id)
    result = 0
    if ship is not None:
        from src.orm.owned_ship import set_ship_favorite
        try:
            set_ship_favorite(ship, flag)
        except Exception:
            result = 1
    else:
        result = 1

    asyncio.create_task(client.send_message(12041, protobuf.SC_12041(result=result)))
    return 0, 12041, None
