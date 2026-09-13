import asyncio
import json
import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

MEDAL_TEMPLATE_CATEGORY = "ShareCfg/medal_template.json"


def handle_claim_trophy(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_17301()
    payload.ParseFromString(buffer)
    response = protobuf.SC_17302(result=1)

    medal_id = payload.id
    if medal_id == 0:
        asyncio.create_task(client.send_message(17302, response))
        return 0, 17302, None

    from src.orm.config_entry import get_config_entry
    try:
        raw = get_config_entry(MEDAL_TEMPLATE_CATEGORY, str(medal_id))
        if raw is None:
            asyncio.create_task(client.send_message(17302, response))
            return 0, 17302, None
        template = raw if isinstance(raw, dict) else json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        asyncio.create_task(client.send_message(17302, response))
        return 0, 17302, None

    commander_id = client.commander.commander_id
    target_num = template.get("target_num", 0)

    from src.orm.commander_trophy_progress import get_or_create_trophy_progress, claim_trophy_progress
    try:
        trophy = get_or_create_trophy_progress(commander_id, medal_id, target_num)
        trophy_id = trophy.get("trophy_id", 0) if isinstance(trophy, dict) else trophy.trophy_id
        trophy_progress = trophy.get("progress", 0) if isinstance(trophy, dict) else trophy.progress
        trophy_timestamp = trophy.get("timestamp", 0) if isinstance(trophy, dict) else trophy.timestamp
        if trophy_timestamp != 0 or trophy_progress < target_num:
            asyncio.create_task(client.send_message(17302, response))
            return 0, 17302, None
    except Exception:
        asyncio.create_task(client.send_message(17302, response))
        return 0, 17302, None

    claim_ts = int(time.time())
    progress_updates = []
    try:
        claim_trophy_progress(commander_id, medal_id, claim_ts)
    except Exception:
        asyncio.create_task(client.send_message(17302, response))
        return 0, 17302, None

    progress_updates.append({
        "trophy_id": medal_id,
        "progress": trophy_progress,
        "timestamp": claim_ts,
    })

    next_id = template.get("next", 0)
    unlocked_next = None
    if next_id != 0:
        next_progress = 0
        if template.get("count_inherit") == next_id:
            next_progress = trophy_progress
        from src.orm.commander_trophy_progress import get_or_create_trophy_progress as get_or_create
        try:
            next_row, created = get_or_create(commander_id, next_id, next_progress), True
            if isinstance(next_row, tuple):
                next_row, created = next_row
            next_row_id = next_row.get("trophy_id", 0) if isinstance(next_row, dict) else next_row.trophy_id
            next_row_progress = next_row.get("progress", 0) if isinstance(next_row, dict) else next_row.progress
            next_row_ts = next_row.get("timestamp", 0) if isinstance(next_row, dict) else next_row.timestamp
            if created:
                next_msg = protobuf.ACHIEVEMENT_INFO()
                next_msg.id = next_row_id
                next_msg.progress = next_row_progress
                next_msg.timestamp = next_row_ts
                unlocked_next = next_msg
                progress_updates.append(next_row)
        except Exception:
            pass

    response.result = 0
    response.timestamp = claim_ts
    if unlocked_next:
        response.next.append(unlocked_next)

    asyncio.create_task(client.send_message(17302, response))

    if progress_updates:
        from .collection_sync import send_trophy_progress_update
        try:
            send_trophy_progress_update(client, progress_updates)
        except Exception:
            pass

    return 0, 17302, None
