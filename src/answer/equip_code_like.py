import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

EQUIP_CODE_LIKE_RESULT_OK = 0
EQUIP_CODE_LIKE_RESULT_ERR = 1
EQUIP_CODE_LIKE_RESULT_ALREADY_LIKE = 7


def handle_equip_code_like(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 17606
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    ship_group_id = payload.get("shipgroup", 0)
    share_id = payload.get("shareid", 0)

    if ship_group_id == 0 or share_id == 0:
        asyncio.create_task(client.send_message(packet_id, protobuf.SC_17606(result=EQUIP_CODE_LIKE_RESULT_ERR)))
        return 0, packet_id, None

    import time
    now = int(time.time())
    day = now // 86400
    commander_id = client.commander.commander_id

    from src.orm.equip_code import try_insert_equip_code_like
    try:
        inserted = try_insert_equip_code_like(commander_id, ship_group_id, share_id, day)
    except Exception as e:
        return 0, packet_id, e

    result = EQUIP_CODE_LIKE_RESULT_ALREADY_LIKE if not inserted else EQUIP_CODE_LIKE_RESULT_OK
    asyncio.create_task(client.send_message(packet_id, protobuf.SC_17606(result=result)))
    return 0, packet_id, None
