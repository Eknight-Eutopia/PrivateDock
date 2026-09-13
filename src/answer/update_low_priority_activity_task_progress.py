import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

PACKET_ID = 20210


def _send_20210(client, result):
    asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_20210(result=result)))


def handle_update_low_priority_activity_task_progress(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from .activity_task_helpers import ACTIVITY_TASK_RESULT_FAILURE, ACTIVITY_TASK_RESULT_SUCCESS

    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, PACKET_ID, e

    updates = payload.get("progressinfo", [])
    if not updates:
        _send_20210(client, ACTIVITY_TASK_RESULT_FAILURE)
        return 0, PACKET_ID, None

    from .activity_task_helpers import load_activity_task_id_set
    activity_task_cache = {}

    for update in updates:
        act_id = update.get("act_id", 0)
        task_id = update.get("task_id", 0)
        mode = update.get("mode", 0)
        if act_id == 0 or task_id == 0:
            _send_20210(client, ACTIVITY_TASK_RESULT_FAILURE)
            return 0, PACKET_ID, None
        from src.orm import ACTIVITY_TASK_PROGRESS_MODE_SET, ACTIVITY_TASK_PROGRESS_MODE_APPEND
        if mode not in (ACTIVITY_TASK_PROGRESS_MODE_SET, ACTIVITY_TASK_PROGRESS_MODE_APPEND):
            _send_20210(client, ACTIVITY_TASK_RESULT_FAILURE)
            return 0, PACKET_ID, None
        if act_id not in activity_task_cache:
            try:
                activity_task_cache[act_id] = load_activity_task_id_set(act_id)
            except Exception as e:
                return 0, PACKET_ID, e
        if task_id not in activity_task_cache[act_id]:
            _send_20210(client, ACTIVITY_TASK_RESULT_FAILURE)
            return 0, PACKET_ID, None

    from src.orm.activity_task import upsert_commander_activity_task_progress
    try:
        for update in updates:
            upsert_commander_activity_task_progress(
                client.commander.commander_id,
                update.get("act_id", 0),
                update.get("task_id", 0),
                update.get("mode", 0),
                update.get("progress", 0),
            )
    except Exception as e:
        return 0, PACKET_ID, e

    _send_20210(client, ACTIVITY_TASK_RESULT_SUCCESS)
    return 0, PACKET_ID, None
