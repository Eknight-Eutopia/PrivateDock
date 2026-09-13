import asyncio
import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

from .helpers import refresh_if_needed


def build_shopping_street_proto(state: dict, goods: list[dict]):
    goods_list = []
    for g in sorted(goods, key=lambda x: x["goods_id"]):
        gproto = protobuf.STREETGOODS()
        gproto.goods_id = g["goods_id"]
        gproto.discount = g["discount"]
        gproto.buy_count = g["buy_count"]
        goods_list.append(gproto)

    street = protobuf.SHOPPINGSTREET()
    street.lv = state.get("level", 1)
    street.next_flash_time = state.get("next_flash_time", 0)
    street.lv_up_time = state.get("level_up_time", 0)
    street.goods_list.extend(goods_list)
    street.flash_count = state.get("flash_count", 0)
    return street


def handle_get_shop_street(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_22101()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 22102, e

    now = int(time.time())

    try:
        state, goods = refresh_if_needed(client.commander.commander_id, now)
    except Exception as e:
        return 0, 22102, e

    response = protobuf.SC_22102()
    street = build_shopping_street_proto(state, goods)
    response.street.CopyFrom(street)

    asyncio.create_task(client.send_message(22102, response))
    return 0, 22102, None
