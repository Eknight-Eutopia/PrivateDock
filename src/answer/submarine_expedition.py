import asyncio
from datetime import datetime, timezone
from typing import Optional

from src.connection.client import Client
from src.orm.submarine_expedition import get_submarine_state, upsert_submarine_state, reset_weekly_refresh, SubmarineExpeditionState
from src.orm.config_entry import list_config_entries

PACKET_ID = 26117

SUBMARINE_DAILY_TEMPLATE_CATEGORY = "ShareCfg/expedition_daily_template.json"
SUBMARINE_DATA_TEMPLATE_CATEGORY = "ShareCfg/expedition_data_template.json"
SUBMARINE_DAILY_EXPEDITION_ID = 501
SUBMARINE_STAGE_TYPE = 15


from src.orm.config_entry import entry_data


def _entry_data(entry):
    return entry_data(entry) or {}


def _load_submarine_chapters() -> list:
    limits = _load_submarine_level_limits()
    entries = list_config_entries(SUBMARINE_DATA_TEMPLATE_CATEGORY)
    chapters = []
    for entry in entries:
        data = _entry_data(entry)
        tid = data.get("id", 0)
        if data.get("type") != SUBMARINE_STAGE_TYPE:
            continue
        if tid < 1000 or tid > 1005:
            continue
        min_level = limits.get(tid)
        if min_level is None:
            continue
        chapters.append({
            "chapter_id": tid,
            "min_level": min_level,
            "index": tid - 1000,
        })
    return chapters


def _load_submarine_level_limits() -> dict:
    entries = list_config_entries(SUBMARINE_DAILY_TEMPLATE_CATEGORY)
    for entry in entries:
        data = _entry_data(entry)
        if str(data.get("id", 0)) != str(SUBMARINE_DAILY_EXPEDITION_ID) and str(entry.key if hasattr(entry, "key") else data.get("id", 0)) != str(SUBMARINE_DAILY_EXPEDITION_ID):
            continue
        limits = {}
        exp_list = data.get("expedition_and_lv_limit_list", [])
        for pair in exp_list:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                limits[int(pair[0])] = int(pair[1])
        return limits
    return {}


def _week_start_monday_utc(now: datetime) -> datetime:
    utc = now.astimezone(timezone.utc)
    start = utc.replace(hour=0, minute=0, second=0, microsecond=0)
    days_since_monday = (start.weekday() - 0 + 7) % 7
    return start.replace(day=start.day - days_since_monday)


def _next_weekly_reset_utc(week_start: datetime) -> datetime:
    return week_start.replace(day=week_start.day + 7)


def _remaining_weekly_refreshes(used: int) -> int:
    if used >= 4:
        return 0
    return 4 - used


def handle_submarine_expedition(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1}))
        return 0, PACKET_ID, None

    now = datetime.now(timezone.utc)
    week_start = _week_start_monday_utc(now)
    week_start_unix = int(week_start.timestamp())

    state = get_submarine_state(client.commander.commander_id)
    if state is None:
        state = SubmarineExpeditionState(
            commander_id=client.commander.commander_id,
            last_refresh_time=week_start_unix,
        )
        upsert_submarine_state(state)

    if state.last_refresh_time < week_start_unix:
        reset_weekly_refresh(client.commander.commander_id, week_start_unix)
        state.weekly_refresh_count = 0
        state.last_refresh_time = week_start_unix

    chapters = _load_submarine_chapters()
    chapter_list = []
    commander_level = client.commander.level
    for chapter in chapters:
        if commander_level < chapter["min_level"]:
            continue
        chapter_list.append({
            "chapter_id": chapter["chapter_id"],
            "active_time": 0,
            "index": chapter["index"],
        })

    refresh_count = _remaining_weekly_refreshes(state.weekly_refresh_count)
    next_refresh = int(_next_weekly_reset_utc(week_start).timestamp())

    response = {
        "next_refresh_time": next_refresh,
        "refresh_count": refresh_count,
        "chapter_list": chapter_list,
        "progress": state.overall_progress,
    }
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
