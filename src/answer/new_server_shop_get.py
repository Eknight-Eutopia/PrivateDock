import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.answer.activity_constants import NEW_SERVER_SHOP_RESULT_OK, NEW_SERVER_SHOP_RESULT_FAILED
from src.answer.new_server_shop_shared import (
    load_new_server_shop_activity,
    default_new_server_shop_state,
    normalize_new_server_shop_state,
    new_server_shop_response_goods,
)
from src.orm import get_new_server_shop_state, upsert_new_server_shop_state

PACKET_ID = 26042


async def _do_get_new_server_shop(client: Client, act_id: int):
    if client.commander is None or act_id == 0:
        await client.send_message(PACKET_ID, protobuf.SC_26042(
            result=NEW_SERVER_SHOP_RESULT_FAILED, start_time=0, stop_time=0, goods=[],
        ))
        return

    activity, active = load_new_server_shop_activity(act_id)
    if not active:
        await client.send_message(PACKET_ID, protobuf.SC_26042(
            result=NEW_SERVER_SHOP_RESULT_FAILED, start_time=0, stop_time=0, goods=[],
        ))
        return

    state = await get_new_server_shop_state(client.commander.commander_id, act_id)
    if state is None:
        state = default_new_server_shop_state(client.commander.commander_id, act_id, activity.goods)
        await upsert_new_server_shop_state(state)

    if normalize_new_server_shop_state(state, activity.goods):
        await upsert_new_server_shop_state(state)

    goods = new_server_shop_response_goods(activity, state)
    await client.send_message(PACKET_ID, protobuf.SC_26042(
        result=NEW_SERVER_SHOP_RESULT_OK,
        start_time=activity.start_time,
        stop_time=activity.stop_time,
        goods=goods,
    ))


def handle_get_new_server_shop(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26041()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e
    asyncio.create_task(_do_get_new_server_shop(client, payload.act_id))
    return 0, PACKET_ID, None
