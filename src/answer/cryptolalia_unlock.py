import asyncio
import json
import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

SOUNDSTORY_TEMPLATE_CATEGORY = "ShareCfg/soundstory_template.json"


def _parse_timer_timestamp(raw) -> Optional[float]:
    try:
        if not isinstance(raw, list) or len(raw) != 2:
            return None
        date = raw[0]
        clock = raw[1]
        if not isinstance(date, list) or len(date) != 3:
            return None
        if not isinstance(clock, list) or len(clock) != 3:
            return None
        year, month, day = int(date[0]), int(date[1]), int(date[2])
        hour, minute, second = int(clock[0]), int(clock[1]), int(clock[2])
        import datetime
        dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _sound_story_time_allows_unlock(raw_time, now: float) -> bool:
    if raw_time is None:
        return False
    if isinstance(raw_time, str):
        return raw_time == "always"
    if isinstance(raw_time, list) and len(raw_time) >= 3:
        name = raw_time[0]
        if not isinstance(name, str) or name != "timer":
            return False
        start = _parse_timer_timestamp(raw_time[1])
        end = _parse_timer_timestamp(raw_time[2])
        if start is None or end is None:
            return False
        return start <= now <= end
    return False


def _select_sound_story_cost(entry: dict, cost_type: int):
    key = f"cost{cost_type}" if cost_type in (1, 2) else None
    if key is None:
        return None
    cost = entry.get(key, [])
    if not isinstance(cost, list) or len(cost) != 3:
        return None
    return {"drop_type": cost[0], "id": cost[1], "amount": cost[2]}


def _load_sound_story_template_entry(story_id: int):
    from src.orm.config_entry import get_config_entry, list_config_entries
    key = str(story_id)
    raw = get_config_entry(SOUNDSTORY_TEMPLATE_CATEGORY, key)
    if raw is not None:
        data = raw.data if hasattr(raw, "data") else (raw if isinstance(raw, dict) else json.loads(raw) if isinstance(raw, str) else raw)
        return data, True
    entries = list_config_entries(SOUNDSTORY_TEMPLATE_CATEGORY)
    for entry in entries:
        data = entry.data if hasattr(entry, "data") else (entry if isinstance(entry, dict) else json.loads(entry) if isinstance(entry, str) else entry)
        if isinstance(data, dict) and data.get("id") == story_id:
            return data, True
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("id") == story_id:
                    return item, True
    return None, False


def handle_cryptolalia_unlock(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_16205()
    payload.ParseFromString(buffer)

    story_id = payload.id
    cost_type = payload.cost_type
    entry, ok = _load_sound_story_template_entry(story_id)
    if not ok:
        asyncio.create_task(client.send_message(16206, protobuf.SC_16206(ret=1)))
        return 0, 16206, None

    now = time.time()
    if not _sound_story_time_allows_unlock(entry.get("time"), now):
        asyncio.create_task(client.send_message(16206, protobuf.SC_16206(ret=2)))
        return 0, 16206, None

    cost = _select_sound_story_cost(entry, cost_type)
    if cost is None:
        asyncio.create_task(client.send_message(16206, protobuf.SC_16206(ret=1)))
        return 0, 16206, None

    from src.orm.item import has_enough_item, consume_item
    from src.orm.resource import has_enough_resource, consume_resource
    from src.orm.commander_story import is_sound_story_unlocked, unlock_sound_story

    try:
        if is_sound_story_unlocked(client.commander.commander_id, story_id):
            asyncio.create_task(client.send_message(16206, protobuf.SC_16206(ret=0)))
            return 0, 16206, None
    except Exception:
        pass

    resource_consumed = False
    try:
        if cost["drop_type"] == 1:
            if not has_enough_resource(client.commander, cost["id"], cost["amount"]):
                asyncio.create_task(client.send_message(16206, protobuf.SC_16206(ret=3)))
                return 0, 16206, None
            consume_resource(client.commander, cost["id"], cost["amount"])
            resource_consumed = True
        elif cost["drop_type"] == 2:
            if not has_enough_item(client.commander, cost["id"], cost["amount"]):
                asyncio.create_task(client.send_message(16206, protobuf.SC_16206(ret=3)))
                return 0, 16206, None
            consume_item(client.commander, cost["id"], cost["amount"])
        else:
            asyncio.create_task(client.send_message(16206, protobuf.SC_16206(ret=1)))
            return 0, 16206, None

        unlock_sound_story(client.commander.commander_id, story_id)
    except Exception:
        asyncio.create_task(client.send_message(16206, protobuf.SC_16206(ret=4)))
        return 0, 16206, None

    asyncio.create_task(client.send_message(16206, protobuf.SC_16206(ret=0)))

    if cost["drop_type"] == 1 and resource_consumed:
        try:
            from . import send_player_resource_sync
            send_player_resource_sync(client)
        except Exception:
            pass

    return 0, 16206, None
