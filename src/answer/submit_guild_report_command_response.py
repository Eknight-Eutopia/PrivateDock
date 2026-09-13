import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.orm.guild_core import get_guild_for_commander
from src.orm.guild_event_operation import claim_guild_reports
from src.answer.meta.helpers import accumulate_drop
from src.logger.logger import log_event, LOG_LEVEL_ERROR
from src.consts.drop_types import (DROP_TYPE_RESOURCE, DROP_TYPE_ITEM, DROP_TYPE_LOVE_LETTER, DROP_TYPE_EQUIP, DROP_TYPE_SHIP, DROP_TYPE_FURNITURE, DROP_TYPE_SKIN, DROP_TYPE_VITEM,
                                   DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE)

PACKET_ID = 72031
GUILD_EVENT_RESULT_SUCCESS = 0
GUILD_EVENT_RESULT_FAILURE = 1


def _normalize_report_ids(ids: list) -> tuple:
    seen = set()
    out = []
    for rid in ids:
        if rid == 0:
            return [], True
        if rid in seen:
            continue
        seen.add(rid)
        out.append(rid)
    return out, False


def _apply_drop_to_commander(client, drop_type: int, drop_id: int, count: int):
    c = client.commander
    if drop_type in (DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE):
        from src.orm.commander_attire import grant_commander_attire_drop_sync
        grant_commander_attire_drop_sync(c.commander_id, drop_type, drop_id, count)
    elif drop_type == DROP_TYPE_RESOURCE:
        c.add_resource(drop_id, count)
    elif drop_type in (DROP_TYPE_ITEM, DROP_TYPE_LOVE_LETTER):
        c.add_item(drop_id, count)
    elif drop_type == DROP_TYPE_EQUIP:
        c.add_owned_equipment(drop_id, count)
    elif drop_type == DROP_TYPE_SHIP:
        for _ in range(count):
            c.add_ship(drop_id)
    elif drop_type == DROP_TYPE_FURNITURE:
        from src.db.session import get_sync_session
        from sqlalchemy import text
        import time
        with get_sync_session() as session:
            session.execute(
                text("""
                    INSERT INTO commander_furnitures (commander_id, furniture_id, count, get_time)
                    VALUES (:cid, :fid, :cnt, :now)
                    ON CONFLICT (commander_id, furniture_id)
                    DO UPDATE SET count = commander_furnitures.count + EXCLUDED.count, get_time = EXCLUDED.get_time
                """),
                {"cid": c.commander_id, "fid": drop_id, "cnt": count, "now": int(time.time())},
            )
            session.commit()
    elif drop_type == DROP_TYPE_SKIN:
        for _ in range(count):
            c.give_skin(drop_id)
    elif drop_type == DROP_TYPE_VITEM:
        pass


def handle_submit_guild_report(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_EVENT_RESULT_FAILURE, "drop_list": []}))
        return 0, PACKET_ID, None

    try:
        data = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_EVENT_RESULT_FAILURE, "drop_list": []}))
        return 0, PACKET_ID, None

    raw_ids = data.get("ids", [])
    ids, invalid = _normalize_report_ids(raw_ids)
    if invalid or not ids:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_EVENT_RESULT_FAILURE, "drop_list": []}))
        return 0, PACKET_ID, None

    guild = get_guild_for_commander(client.commander.commander_id)
    if guild is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_EVENT_RESULT_FAILURE, "drop_list": []}))
        return 0, PACKET_ID, None

    try:
        reports = claim_guild_reports(guild.id, ids)
    except Exception as e:
        log_event("GuildReport", "Claim", f"claim failed: {e}", LOG_LEVEL_ERROR)
        asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_EVENT_RESULT_FAILURE, "drop_list": []}))
        return 0, PACKET_ID, None

    drop_map = {}
    for report in reports:
        if report.get("drop_count", 0) == 0:
            continue
        drop_type = report.get("drop_type", 0)
        drop_id = report.get("drop_id", 0)
        drop_count = report.get("drop_count", 0)
        accumulate_drop(drop_map, drop_type, drop_id, drop_count)

    if drop_map:
        for drop in drop_map.values():
            _apply_drop_to_commander(client, drop.type, drop.id, drop.number)

    drop_list = [{"type": d.type, "id": d.id, "number": d.number} for d in drop_map.values()]
    drop_list.sort(key=lambda x: (x["type"], x["id"]))
    response = {"result": GUILD_EVENT_RESULT_SUCCESS, "drop_list": drop_list}
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
