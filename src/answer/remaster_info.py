import asyncio
from typing import Optional

from src.connection.client import Client
from src.orm.remaster_progress import list_remaster_progress
from src.orm.config_entry import list_config_entries_sync
from src.protobuf import protobuf

RESPONSE_PACKET_ID = 13506
REMASTER_CONFIG_CATEGORY = "ShareCfg/re_map_template.json"


def _build_gains():
    config_entries = list_config_entries_sync(REMASTER_CONFIG_CATEGORY)
    gains = []
    for entry in config_entries:
        template = entry.data if isinstance(entry.data, dict) else {}
        drop_gain = template.get("drop_gain", [])
        for index, gain in enumerate(drop_gain):
            if not gain or len(gain) < 4:
                continue
            gains.append({
                "chapter_id": gain[0],
                "pos": index + 1,
                "drop_type": gain[1],
                "drop_id": gain[2],
                "max_count": gain[3],
            })
    return gains


def handle_remaster_request_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_13505()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, RESPONSE_PACKET_ID, e

    commander_id = client.commander.commander_id

    progress_list = list_remaster_progress(commander_id)
    progress_map = {}
    for p in progress_list:
        progress_map[(p.chapter_id, p.pos)] = p

    gains = _build_gains()
    response = protobuf.SC_13506()
    for gain in gains:
        key = (gain["chapter_id"], gain["pos"])
        progress_entry = progress_map.get(key)
        count = progress_entry.count if progress_entry else 0
        flag = 1 if (progress_entry and progress_entry.received) else 0
        remap = protobuf.REMAPCOUNT(
            chapter_id=gain["chapter_id"],
            pos=gain["pos"],
            count=count,
            flag=flag,
        )
        response.remap_count_list.append(remap)

    asyncio.create_task(client.send_message(RESPONSE_PACKET_ID, response))
    return 0, RESPONSE_PACKET_ID, None
