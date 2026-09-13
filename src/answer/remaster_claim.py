import asyncio
from typing import Optional

from src.connection.client import Client
from src.orm.remaster_progress import (
    get_remaster_progress,
    upsert_remaster_progress,
    RemasterProgress,
)
from src.orm.config_entry import list_config_entries_sync
from src.protobuf import protobuf
from src.logger.logger import log_event, LOG_LEVEL_INFO

PACKET_ID = 13508
REMASTER_CONFIG_CATEGORY = "ShareCfg/re_map_template.json"


def _find_gain_config(chapter_id: int, pos: int):
    entries = list_config_entries_sync(REMASTER_CONFIG_CATEGORY)
    for entry in entries:
        template = entry.data if isinstance(entry.data, dict) else {}
        drop_gain = template.get("drop_gain", [])
        for index, gain in enumerate(drop_gain):
            if not gain or len(gain) < 4:
                continue
            if gain[0] == chapter_id and (index + 1) == pos:
                return {"chapter_id": gain[0], "pos": index + 1, "drop_type": gain[1], "drop_id": gain[2], "max_count": gain[3]}
    return None


def handle_remaster_claim(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_13508(result=1)))
        return 0, PACKET_ID, None

    try:
        payload = protobuf.CS_13507()
        payload.ParseFromString(buffer)
    except Exception:
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_13508(result=1)))
        return 0, PACKET_ID, None

    chapter_id = payload.chapter_id
    pos = payload.pos

    config = _find_gain_config(chapter_id, pos)
    if config is None:
        log_event("Remaster", "Claim", f"no config for ch={chapter_id} pos={pos}", LOG_LEVEL_INFO)
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_13508(result=1)))
        return 0, PACKET_ID, None

    progress = get_remaster_progress(client.commander.commander_id, config["chapter_id"], config["pos"])
    if progress is None:
        progress = RemasterProgress(
            commander_id=client.commander.commander_id,
            chapter_id=config["chapter_id"],
            pos=config["pos"],
            count=0,
            received=False,
        )

    if progress.received or progress.count < config["max_count"]:
        log_event("Remaster", "Claim", f"not claimable: received={progress.received} count={progress.count} max={config['max_count']}", LOG_LEVEL_INFO)
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_13508(result=1)))
        return 0, PACKET_ID, None

    c = client.commander
    drop_type = config["drop_type"]
    drop_id = config["drop_id"]

    if drop_type == 1:
        c.add_resource(drop_id, 1)
    elif drop_type == 2:
        c.add_item(drop_id, 1)
    elif drop_type == 4:
        c.add_ship(drop_id)
    elif drop_type == 7:
        c.give_skin(drop_id)

    progress.received = True
    upsert_remaster_progress(progress)

    response = protobuf.SC_13508(result=0)
    entry = response.drop_list.add()
    entry.type = drop_type
    entry.id = drop_id
    entry.number = 1

    asyncio.create_task(client.send_message(PACKET_ID, response))
    log_event("Remaster", "Claim", f"claimed ch={chapter_id} pos={pos} type={drop_type} id={drop_id}", LOG_LEVEL_INFO)
    return 0, PACKET_ID, None
