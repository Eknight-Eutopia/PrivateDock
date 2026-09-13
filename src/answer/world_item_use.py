import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.orm.config_entry import get_config_entry_sync
from src.orm.item import consume_commander_item, get_commander_item_count
from src.orm.world_runtime import (
    load_or_create_world_runtime,
    save_world_runtime,
    sync_world_runtime,
)


PACKET_ID = 19491


def _world_gameset_key_value(key: str) -> int:
    for cat in ("ShareCfg/gameset.json", "sharecfgdata/gameset.json"):
        entry = get_config_entry_sync(cat, key)
        if entry is not None and entry.data:
            val = entry.data.get("key_value", 0)
            if val:
                return int(val) if not isinstance(val, (list, dict)) else 0
    return 0


def handle_world_item_use(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, PACKET_ID, e

    item_id = int(payload.get("id", 0))
    count = int(payload.get("count", 0))

    if item_id == 0 or count == 0:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1}))
        return 0, PACKET_ID, None

    entry = get_config_entry_sync("ShareCfg/world_item_data_template.json", str(item_id))
    if entry is None or entry.data is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1}))
        return 0, PACKET_ID, None

    config = entry.data
    usage = config.get("usage", "")

    has_item = get_commander_item_count(client.commander.commander_id, item_id) >= count
    if not has_item:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1}))
        return 0, PACKET_ID, None

    if usage == "usage_world_recoverAP":
        usage_arg = config.get("usage_arg", [])
        if isinstance(usage_arg, list) and len(usage_arg) > 0 and usage_arg[0] > 0:
            recover_gain = int(usage_arg[0]) * count
            if recover_gain > 0:
                from datetime import datetime, timezone
                runtime = load_or_create_world_runtime(client.commander.commander_id)
                now = datetime.now(timezone.utc)
                sync_world_runtime(runtime, now=now)
                max_power = _world_gameset_key_value("world_movepower_maxvalue") or 200
                runtime.action_power += recover_gain
                if runtime.action_power >= max_power:
                    runtime.last_recover_timestamp = int(now.timestamp())
                save_world_runtime(runtime)

    consume_commander_item(client.commander.commander_id, item_id, count)

    if client.commander is not None:
        items_map = getattr(client.commander, "commander_items_map", None) or {}
        if item_id in items_map:
            if items_map[item_id]["count"] <= count:
                del items_map[item_id]
            else:
                items_map[item_id]["count"] -= count

    asyncio.create_task(client.send_message(PACKET_ID, {"result": 0}))
    return 0, PACKET_ID, None
