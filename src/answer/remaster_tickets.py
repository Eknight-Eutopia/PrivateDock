import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.orm.remaster import get_or_create_remaster_state, update_remaster_tickets_sync
from .remaster_config import load_gameset_value

PACKET_ID = 24612


def handle_remaster_request_tickets(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1}))
        return 0, PACKET_ID, None

    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception:
        payload = {}

    state = get_or_create_remaster_state(client.commander.commander_id)

    daily = load_gameset_value("reactivity_ticket_daily")
    max_tickets = load_gameset_value("reactivity_ticket_max")
    if daily is None or max_tickets is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1}))
        return 0, PACKET_ID, None

    response = {"result": 1}
    req_type = payload.get("type", 1)
    if req_type != 0:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    if state.daily_count > 0:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    if state.ticket_count >= max_tickets:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    grant = daily
    remaining = max_tickets - state.ticket_count
    if remaining < grant:
        grant = remaining
    if grant == 0:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    state.ticket_count += grant
    state.daily_count = daily
    update_remaster_tickets_sync(client.commander.commander_id, state.ticket_count, state.daily_count)

    response = {"result": 0}
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
