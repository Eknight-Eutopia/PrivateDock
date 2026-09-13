import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from src.connection.client import Client
from src.answer.feast_helpers import (
    FEAST_FAILURE_RESULT,
    is_feast_activity_active,
    flatten_uint_set_from_json,
    feast_party_roles_to_proto,
)
from src.protobuf import protobuf


def handle_feast_random_ships(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 26159, e

    act_id = payload.get("act_id", 0)
    if act_id == 0:
        asyncio.create_task(client.send_message(26159, protobuf.SC_26159(ret=FEAST_FAILURE_RESULT)))
        return 0, 26159, None

    try:
        active, template = is_feast_activity_active(act_id, datetime.now(timezone.utc))
    except Exception as e:
        return 0, 26159, e

    if not active:
        asyncio.create_task(client.send_message(26159, protobuf.SC_26159(ret=FEAST_FAILURE_RESULT)))
        return 0, 26159, None

    ship_group_ids = payload.get("ship_group_id", [])
    allowed = set()
    if template is not None:
        allowed = flatten_uint_set_from_json(template.get("config_data"))

    party_roles = _build_feast_party_roles(ship_group_ids, allowed)
    if party_roles is None:
        asyncio.create_task(client.send_message(26159, protobuf.SC_26159(ret=FEAST_FAILURE_RESULT)))
        return 0, 26159, None

    from src.orm import get_or_create_feast_state, save_feast_state

    try:
        state = get_or_create_feast_state(client.commander.commander_id, act_id)
    except Exception as e:
        return 0, 26159, e

    now_unix = int(datetime.now(timezone.utc).timestamp())
    if state.get("refresh_time", 0) > now_unix:
        asyncio.create_task(client.send_message(26159, protobuf.SC_26159(ret=FEAST_FAILURE_RESULT)))
        return 0, 26159, None

    state["party_roles"] = party_roles
    state["refresh_time"] = now_unix + 3600

    try:
        save_feast_state(state)
    except Exception as e:
        return 0, 26159, e

    resp = protobuf.SC_26159(ret=0, refresh_time=state["refresh_time"])
    for r in feast_party_roles_to_proto(state["party_roles"]):
        resp.party_roles.append(r)

    asyncio.create_task(client.send_message(26159, resp))
    return 0, 26159, None


def _build_feast_party_roles(ship_group_ids: list, allowed: set):
    if not ship_group_ids:
        return None
    seen = set()
    roles = []
    for ship_group_id in ship_group_ids:
        if ship_group_id == 0:
            return None
        if ship_group_id in seen:
            return None
        if allowed and ship_group_id not in allowed:
            return None
        seen.add(ship_group_id)
        roles.append({"tid": ship_group_id, "bubble": 0, "speech_bubble": 0})
    roles.sort(key=lambda r: r["tid"])
    return roles
