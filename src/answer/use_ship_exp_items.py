import asyncio
from typing import Optional

from src.connection.client import Client
from src.db.session import get_sync_session
from src.protobuf import protobuf
from src.answer.lesson_resource_packet_helpers import (
    load_ship_exp_book_set,
    load_item_statistics_config,
    parse_usage_arg_exp_value,
)
from src.answer.meta.helpers import normalize_ship_exp_books
from src.answer.event_finish import _apply_owned_ship_exp_gain
from sqlalchemy import text

PACKET_ID = 22012


def handle_use_ship_exp_items(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_22011.FromString(buffer)
    except Exception as e:
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_22012(result=1)))
        return 0, PACKET_ID, e

    response = protobuf.SC_22012(result=1)

    c = client.commander
    if c.owned_ships_map is None or c.commander_items_map is None or c.misc_items_map is None:
        try:
            c.load()
        except Exception as e:
            asyncio.create_task(client.send_message(PACKET_ID, response))
            return 0, PACKET_ID, e

    ship_id = payload.ship_id
    if ship_id == 0:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    owned = c.owned_ships_map.get(ship_id)
    if owned is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    book_counts, ok = normalize_ship_exp_books(payload.books)
    if not ok:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    book_set = load_ship_exp_book_set()
    if book_set is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    total_exp = 0
    for item_id, count in book_counts.items():
        if item_id not in book_set:
            asyncio.create_task(client.send_message(PACKET_ID, response))
            return 0, PACKET_ID, None
        if not c.has_enough_item(item_id, count):
            asyncio.create_task(client.send_message(PACKET_ID, response))
            return 0, PACKET_ID, None
        item_config = load_item_statistics_config(item_id)
        if item_config is None:
            asyncio.create_task(client.send_message(PACKET_ID, response))
            return 0, PACKET_ID, None
        usage_arg = item_config.get("usage_arg", item_config.get("UsageArg"))
        exp_per_item = parse_usage_arg_exp_value(usage_arg)
        if exp_per_item == 0:
            asyncio.create_task(client.send_message(PACKET_ID, response))
            return 0, PACKET_ID, None
        total_exp += exp_per_item * count

    old_level = owned.get("level", 0)
    old_exp = owned.get("exp", 0)
    old_surplus = owned.get("surplus_exp", 0)

    mock = dict(owned)
    mock["level"] = old_level
    mock["exp"] = old_exp
    mock["surplus_exp"] = old_surplus
    mock["max_level"] = owned.get("max_level", 100)

    _apply_owned_ship_exp_gain(client, mock, total_exp)
    new_level = mock["level"]
    new_exp = mock["exp"]
    new_surplus = mock["surplus_exp"]

    if new_level == old_level and new_exp == old_exp and new_surplus == old_surplus:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    ship_row_id = owned.get("id", owned.get("ship_id", ship_id))
    try:
        with get_sync_session() as session:
            for item_id, count in book_counts.items():
                c.consume_item(item_id, count)
            session.execute(
                text("UPDATE owned_ships SET level = :lvl, exp = :exp, surplus_exp = :surp "
                     "WHERE owner_id = :cid AND id = :sid"),
                {"lvl": new_level, "exp": new_exp, "surp": new_surplus,
                 "cid": c.commander_id, "sid": ship_row_id},
            )
            session.commit()
    except Exception as e:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, e

    owned["level"] = new_level
    owned["exp"] = new_exp
    owned["surplus_exp"] = new_surplus

    response = protobuf.SC_22012(result=0)
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
