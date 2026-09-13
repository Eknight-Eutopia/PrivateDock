import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.orm.remaster_progress import get_remaster_progress, upsert_remaster_progress, RemasterProgress
from src.logger.logger import log_event, LOG_LEVEL_INFO, LOG_LEVEL_ERROR
from .remaster_config import list_remaster_drop_gains, build_remaster_drop_gain_map

PACKET_ID = 24616


def handle_remaster_request_award_receive(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": 1, "drop_list": []}))
        return 0, PACKET_ID, None

    log_event("Remaster", "AwardReceive", f"buffer={buffer.hex()} len={len(buffer)}", LOG_LEVEL_INFO)
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        log_event("Remaster", "AwardReceive", f"json parse failed: {e}", LOG_LEVEL_ERROR)
        payload = {}

    chapter_id = payload.get("chapter_id", 0)
    pos = payload.get("pos", 0)
    log_event("Remaster", "AwardReceive", f"chapter_id={chapter_id} pos={pos} keys={list(payload.keys())}", LOG_LEVEL_INFO)

    gains = list_remaster_drop_gains()
    lookup = build_remaster_drop_gain_map(gains)
    key = (chapter_id, pos)
    config = lookup.get(key)

    response = {"result": 1, "drop_list": []}
    if config is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    progress = get_remaster_progress(client.commander.commander_id, config.chapter_id, config.pos)
    if progress is None:
        progress = RemasterProgress(
            commander_id=client.commander.commander_id,
            chapter_id=config.chapter_id,
            pos=config.pos,
            count=0,
            received=False,
        )

    if progress.received or progress.count < config.max_count:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    c = client.commander
    if not hasattr(c, "get_item_count") or not hasattr(c, "get_resource_count"):
        log_event("Remaster", "Award", "commander maps missing, reloading commander", LOG_LEVEL_INFO)
        try:
            c.load()
        except Exception as e:
            log_event("Remaster", "Award", "commander load failed", LOG_LEVEL_ERROR)
            asyncio.create_task(client.send_message(PACKET_ID, response))
            return 0, PACKET_ID, e

    drop_type = config.drop_type
    drop_id = config.drop_id
    drop = {"type": drop_type, "id": drop_id, "number": 1}

    if drop_type == 1:
        c.add_resource(drop_id, 1)
    elif drop_type == 2:
        c.add_item(drop_id, 1)
    elif drop_type == 4:
        c.add_ship(drop_id)
    elif drop_type == 7:
        c.give_skin(drop_id)
    elif drop_type == 8:
        pass
    elif drop_type in (14, 15, 31):
        from src.orm.commander_attire import grant_commander_attire_drop_sync
        grant_commander_attire_drop_sync(c.commander_id, drop_type, drop_id, 1)

    progress.received = True
    upsert_remaster_progress(progress)

    response = {"result": 0, "drop_list": [drop]}
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
