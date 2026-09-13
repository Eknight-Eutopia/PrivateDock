import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from src.connection.client import Client
from src.answer.feast_helpers import (
    FEAST_FAILURE_RESULT,
    is_feast_activity_active,
    feast_party_roles_to_proto,
    feast_special_roles_to_proto,
)
from src.protobuf import protobuf


def handle_feast_get_data(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 26157, e

    act_id = payload.get("act_id", 0)
    if act_id == 0:
        asyncio.create_task(client.send_message(26157, protobuf.SC_26157(ret=FEAST_FAILURE_RESULT)))
        return 0, 26157, None

    try:
        active, _ = is_feast_activity_active(act_id, datetime.now(timezone.utc))
    except Exception as e:
        return 0, 26157, e

    if not active:
        asyncio.create_task(client.send_message(26157, protobuf.SC_26157(ret=FEAST_FAILURE_RESULT)))
        return 0, 26157, None

    from src.orm import get_or_create_feast_state

    try:
        state = get_or_create_feast_state(client.commander.commander_id, act_id)
    except Exception as e:
        return 0, 26157, e

    resp = protobuf.SC_26157(ret=0)
    for r in feast_party_roles_to_proto(state.get("party_roles", [])):
        resp.party_roles.append(r)
    for r in feast_special_roles_to_proto(state.get("special_roles", [])):
        resp.special_roles.append(r)
    if state.get("refresh_time", 0) > 0:
        resp.refresh_time = state["refresh_time"]

    asyncio.create_task(client.send_message(26157, resp))
    return 0, 26157, None
