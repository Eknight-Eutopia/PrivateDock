import asyncio
from typing import Optional

from src.connection.client import Client
from src.orm.remaster import (
    apply_remaster_daily_reset,
    get_or_create_remaster_state,
    update_remaster_tickets_sync,
)
from src.protobuf import protobuf
from .remaster_config import load_gameset_value

RESPONSE_PACKET_ID = 13504


def handle_remaster_basic_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, protobuf.SC_13504(result=1)))
        return 0, RESPONSE_PACKET_ID, None

    try:
        payload = protobuf.CS_13503()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, RESPONSE_PACKET_ID, e

    commander_id = client.commander.commander_id
    state = get_or_create_remaster_state(commander_id)
    state = apply_remaster_daily_reset(commander_id) or state

    daily = load_gameset_value("reactivity_ticket_daily")
    max_tickets = load_gameset_value("reactivity_ticket_max")
    if daily is None or max_tickets is None:
        asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, protobuf.SC_13504(result=1)))
        return 0, RESPONSE_PACKET_ID, None

    req_type = payload.type
    if req_type != 0:
        asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, protobuf.SC_13504(result=1)))
        return 0, RESPONSE_PACKET_ID, None

    if state.daily_count > 0:
        asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, protobuf.SC_13504(result=1)))
        return 0, RESPONSE_PACKET_ID, None

    if state.ticket_count >= max_tickets:
        asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, protobuf.SC_13504(result=1)))
        return 0, RESPONSE_PACKET_ID, None

    grant = daily
    remaining = max_tickets - state.ticket_count
    if remaining < grant:
        grant = remaining
    if grant <= 0:
        asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, protobuf.SC_13504(result=1)))
        return 0, RESPONSE_PACKET_ID, None

    state.ticket_count += grant
    state.daily_count = daily
    update_remaster_tickets_sync(commander_id, state.ticket_count, state.daily_count)

    response = protobuf.SC_13504(result=0)
    asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, response))
    return 0, RESPONSE_PACKET_ID, None
