import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

COMMANDER_RESULT_OK = 0
COMMANDER_RESULT_ERROR = 1

_DEFAULT_COST_CURVE = [300, 600, 900, 1200, 1500, 1800]


def _load_commander_reserve_cost_curve() -> list:
    try:
        from src.orm.config_entry import get_config_entry
        entry = get_config_entry("ShareCfg/gameset.json", "commander_get_cost")
        if entry:
            data = entry.get("data", "{}") if isinstance(entry, dict) else getattr(entry, "data", "{}")
            if isinstance(data, str):
                payload = json.loads(data)
            else:
                payload = data
            description = payload.get("description", [])
            if description:
                return description
    except Exception:
        pass
    return list(_DEFAULT_COST_CURVE)


def handle_commander_reserve_box(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25018()
    payload.ParseFromString(buffer)

    count = payload.type
    if count == 0:
        asyncio.create_task(client.send_message(25019, protobuf.SC_25019(result=COMMANDER_RESULT_ERROR)))
        return 0, 25019, None

    cost_curve = _load_commander_reserve_cost_curve()
    usage = getattr(client.commander, "draw_count1", 0)
    if usage + count > len(cost_curve):
        asyncio.create_task(client.send_message(25019, protobuf.SC_25019(result=COMMANDER_RESULT_ERROR)))
        return 0, 25019, None

    total_cost = sum(cost_curve[usage:usage + count])

    try:
        if not client.commander.has_enough_gold(total_cost):
            asyncio.create_task(client.send_message(25019, protobuf.SC_25019(result=COMMANDER_RESULT_ERROR)))
            return 0, 25019, None
        client.commander.consume_resource(1, total_cost)
    except Exception:
        pass

    try:
        client.commander.increment_reserve_usage(count)
    except Exception:
        pass

    try:
        client.commander.add_item(20001, count)
    except Exception:
        pass

    response = protobuf.SC_25019(result=COMMANDER_RESULT_OK)
    for _ in range(count):
        award = protobuf.DROPINFO(type=2, id=20001, number=1)
        response.awards.append(award)
    asyncio.create_task(client.send_message(25019, response))
    return 0, 25019, None
