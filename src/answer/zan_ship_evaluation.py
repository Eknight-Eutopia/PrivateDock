from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_zan_ship_evaluation(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    import json
    import asyncio
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    if client.commander is None:
        asyncio.create_task(client.send_message(17106, protobuf.SC_17106(result=1)))
        return 0, 17106, None

    ship_group_id = payload.get("ship_group_id", 0)
    discuss_id = payload.get("discuss_id", 0)
    good_or_bad = payload.get("good_or_bad", 0)

    if ship_group_id == 0 or discuss_id == 0:
        asyncio.create_task(client.send_message(17106, protobuf.SC_17106(result=1)))
        return 0, 17106, None

    if good_or_bad not in (0, 1):
        asyncio.create_task(client.send_message(17106, protobuf.SC_17106(result=1)))
        return 0, 17106, None

    from .evaluate_ship import _get_ship_discuss_state
    state = _get_ship_discuss_state(ship_group_id)

    with state.lock:
        entry = None
        for e in state.discuss_list:
            if e.get("id") == discuss_id:
                entry = e
                break

        if entry is None:
            asyncio.create_task(client.send_message(17106, protobuf.SC_17106(result=1)))
            return 0, 17106, None

        commander_id = client.commander.commander_id
        if state.reviewed_discuss_by_commander is not None:
            voted = state.reviewed_discuss_by_commander.get(commander_id)
            if voted is not None and discuss_id in voted:
                asyncio.create_task(client.send_message(17106, protobuf.SC_17106(result=7)))
                return 0, 17106, None

        if good_or_bad == 0:
            entry["good_count"] = entry.get("good_count", 0) + 1
        else:
            entry["bad_count"] = entry.get("bad_count", 0) + 1

        if state.reviewed_discuss_by_commander is None:
            state.reviewed_discuss_by_commander = {}
        if commander_id not in state.reviewed_discuss_by_commander:
            state.reviewed_discuss_by_commander[commander_id] = set()
        state.reviewed_discuss_by_commander[commander_id].add(discuss_id)

    asyncio.create_task(client.send_message(17106, protobuf.SC_17106(result=0)))
    return 0, 17106, None
