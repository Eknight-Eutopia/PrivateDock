import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.orm.config_entry import get_config_entry_sync
from src.orm.world_runtime import (
    load_or_create_world_runtime,
    save_world_runtime,
    sync_world_runtime,
    map_template as runtime_map_template,
    set_map_template as runtime_set_map_template,
)


def _resolve_map_template_id(random_id: int) -> int:
    if random_id == 0:
        return 0
    for cat in ("ShareCfg/world_chapter_random.json", "sharecfgdata/world_chapter_random.json"):
        entry = get_config_entry_sync(cat, str(random_id))
        if entry is not None and entry.data:
            cfg = entry.data
            for key in ("template_id", "map", "map_id", "chapter_id", "id"):
                val = cfg.get(key, 0)
                if val:
                    return int(val)
    return random_id


def handle_world_core_get_data(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 19507, e

    map_id = int(payload.get("id", 0))
    if map_id == 0:
        asyncio.create_task(client.send_message(19507, protobuf.SC_19507(result=0)))
        return 0, 19507, None

    runtime = load_or_create_world_runtime(client.commander.commander_id)
    now = datetime.now(timezone.utc)
    changed, _ = sync_world_runtime(runtime, now=now)

    template_id = runtime_map_template(runtime, map_id)
    if template_id == 0:
        template_id = _resolve_map_template_id(map_id)
        if template_id:
            runtime_set_map_template(runtime, map_id, template_id)
            changed = True

    if changed:
        save_world_runtime(runtime)

    asyncio.create_task(client.send_message(19507, protobuf.SC_19507(result=0)))
    return 0, 19507, None


def handle_world_core_open_core(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 19509, e

    target_map_id = int(payload.get("map_id", 0))

    runtime = load_or_create_world_runtime(client.commander.commander_id)
    now = datetime.now(timezone.utc)
    sync_world_runtime(runtime, now=now)

    if runtime.action_power == 0:
        asyncio.create_task(client.send_message(19509, {"result": 1, "data": []}))
        return 0, 19509, None

    runtime.action_power -= 1

    if target_map_id > 0:
        template_id = runtime_map_template(runtime, target_map_id)
        if template_id == 0:
            template_id = _resolve_map_template_id(target_map_id)
            if template_id:
                runtime_set_map_template(runtime, target_map_id, template_id)
        runtime.map_id = target_map_id
        runtime.enter_map_id = target_map_id
        runtime.last_change_group_timestamp = int(now.timestamp())

    save_world_runtime(runtime)

    asyncio.create_task(client.send_message(19509, {"result": 0, "data": []}))
    return 0, 19509, None
