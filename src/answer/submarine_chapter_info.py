import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from src.connection.client import Client
from src.orm.remaster import apply_remaster_daily_reset, get_or_create_remaster_state
from src.orm.config_entry import list_config_entries

PACKET_ID = 26115
ESCORT_MAP_TEMPLATE_CATEGORY = "ShareCfg/escort_map_template.json"


from src.orm.config_entry import entry_data


def _entry_data(entry):
    return entry_data(entry) or {}


def _resolve_active_submarine_chapter(now: datetime) -> tuple:
    entries = list_config_entries(ESCORT_MAP_TEMPLATE_CATEGORY)
    for entry in entries:
        data = _entry_data(entry)
        refresh_time = data.get("refresh_time", 0)
        escort_id_list = data.get("escort_id_list", [])
        escort_ids = _parse_escort_id_list(escort_id_list)
        if not escort_ids or refresh_time == 0:
            continue
        now_unix = int(now.timestamp())
        slot_index = (now_unix // refresh_time) % len(escort_ids)
        slot_start = now_unix - (now_unix % refresh_time)
        return escort_ids[slot_index], slot_start, slot_index + 1, True
    return 0, 0, 0, False


def _parse_escort_id_list(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        if raw and isinstance(raw[0], list):
            flat = []
            for group in raw:
                flat.extend(group)
            return flat
        return raw
    return []


def handle_submarine_chapter_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1}))
        return 0, PACKET_ID, None

    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception:
        payload = {}

    state = get_or_create_remaster_state(client.commander.commander_id)

    now = datetime.now(timezone.utc)
    apply_remaster_daily_reset(client.commander.commander_id)

    response = {"result": 1}

    req_type = payload.get("type", 1)
    if req_type != 0:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    chapter_id, active_at, index, ok = _resolve_active_submarine_chapter(now)
    if not ok:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    response = {
        "result": 0,
        "chapter_id": {
            "chapter_id": chapter_id,
            "active_time": active_at,
            "index": index,
        },
    }
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
