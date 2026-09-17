import asyncio
import random
from typing import Optional

from src.connection.client import Client
from src.orm.commander_box_daily import (
    get_commander_box_daily_usage,
    increment_commander_box_daily_usage,
)
from src.protobuf import protobuf

COMMANDER_RESULT_OK = 0
COMMANDER_RESULT_ERROR = 1

MAX_GETBOX_CNT = 15


def get_box_cost(idx: int) -> int:
    # First box of the day (index 0) is free (0 gold), subsequent boxes (1..14) cost 1500 gold.
    return 0 if idx < 1 else 1500


def handle_commander_reserve_box(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25018()
    payload.ParseFromString(buffer)

    count = payload.type
    if count <= 0:
        asyncio.create_task(client.send_message(25019, protobuf.SC_25019(result=COMMANDER_RESULT_ERROR)))
        return 0, 25019, None

    cid = client.commander.commander_id
    usage = get_commander_box_daily_usage(cid)
    if usage + count > MAX_GETBOX_CNT:
        asyncio.create_task(client.send_message(25019, protobuf.SC_25019(result=COMMANDER_RESULT_ERROR)))
        return 0, 25019, None

    total_cost = sum(get_box_cost(usage + i) for i in range(count))

    if not client.commander.has_enough_gold(total_cost):
        asyncio.create_task(client.send_message(25019, protobuf.SC_25019(result=COMMANDER_RESULT_ERROR)))
        return 0, 25019, None

    if total_cost > 0:
        try:
            client.commander.consume_resource(1, total_cost)
        except Exception:
            pass

    increment_commander_box_daily_usage(cid, count)

    response = protobuf.SC_25019(result=COMMANDER_RESULT_OK)
    for _ in range(count):
        roll = random.random() * 100
        if roll < 60.0:
            item_id = 20011  # Rare Cat Box (R)
        elif roll < 95.0:
            item_id = 20012  # Elite Cat Box (SR)
        else:
            item_id = 20013  # Super Rare Cat Box (SSR)

        try:
            client.commander.add_item(item_id, 1)
        except Exception:
            pass

        award = protobuf.DROPINFO(type=2, id=item_id, number=1)
        response.awards.append(award)

    asyncio.create_task(client.send_message(25019, response))
    return 0, 25019, None
