import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_retire_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12004.FromString(buffer)
    ship_ids = list(payload.ship_id_list)
    result = 0
    try:
        if not ship_ids:
            result = 1
        else:
            from src.orm.owned_ship import retire_ships
            retire_ships(client.commander, ship_ids)
    except Exception:
        result = 1

    resp = protobuf.SC_12005(result=result)
    if result == 0:
        resp.ship_id_list.extend(ship_ids)
        # Task progress: retiring ships advances every "Retire X ships" task
        # (sub_type 31) by the number of ships retired.
        try:
            from src.answer.task_handlers import schedule_emit
            schedule_emit(client, 31, 0, len(ship_ids))
        except Exception:
            pass
    asyncio.create_task(client.send_message(12005, resp))
    return 0, 12005, None
