import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_quick_finish_activity_task(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from .activity_task_helpers import (
        ACTIVITY_TASK_RESULT_FAILURE,
        ACTIVITY_TASK_RESULT_SUCCESS,
        QUICK_TASK_TICKET_ITEM_ID,
        load_activity_task_id_set,
        load_activity_task_template,
        build_award_drop_map,
        activity_drop_map_to_sorted_list,
    )

    PACKET_ID = 20208

    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, PACKET_ID, e

    act_id = payload.get("act_id", 0)
    task_id = payload.get("task_id", 0)
    item_cost = payload.get("item_cost", 0)
    if act_id == 0 or task_id == 0 or item_cost == 0:
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_20208(result=ACTIVITY_TASK_RESULT_FAILURE)))
        return 0, PACKET_ID, None

    try:
        activity_task_ids = load_activity_task_id_set(act_id)
    except Exception as e:
        return 0, PACKET_ID, e

    if task_id not in activity_task_ids:
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_20208(result=ACTIVITY_TASK_RESULT_FAILURE)))
        return 0, PACKET_ID, None

    try:
        template = load_activity_task_template(task_id)
    except Exception as e:
        return 0, PACKET_ID, e

    quick_finish = template.get("quick_finish", 0)
    if quick_finish == 0 or quick_finish != item_cost:
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_20208(result=ACTIVITY_TASK_RESULT_FAILURE)))
        return 0, PACKET_ID, None

    try:
        drops = build_award_drop_map(template.get("award_display", []))
    except Exception as e:
        return 0, PACKET_ID, e

    from src.orm.activity_task import try_submit_commander_activity_task
    import concurrent.futures

    def _exec():
        submitted = try_submit_commander_activity_task(
            client.commander.commander_id, act_id, task_id
        )
        if not submitted:
            return False
        if not client.commander.has_enough_item(QUICK_TASK_TICKET_ITEM_ID, item_cost):
            return False
        client.commander.consume_item(QUICK_TASK_TICKET_ITEM_ID, item_cost)
        from src.answer.activity_task_helpers import apply_activity_task_drops
        apply_activity_task_drops(client.commander, drops)
        return True

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            ok = pool.submit(_exec).result()
            if not ok:
                asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_20208(result=ACTIVITY_TASK_RESULT_FAILURE)))
                return 0, PACKET_ID, None
    except Exception as e:
        return 0, PACKET_ID, e

    try:
        client.commander.load()
    except Exception as e:
        return 0, PACKET_ID, e

    resp = protobuf.SC_20208(result=ACTIVITY_TASK_RESULT_SUCCESS)
    award_list = activity_drop_map_to_sorted_list(drops)
    for a in award_list:
        resp.award_list.append(a)
    asyncio.create_task(client.send_message(PACKET_ID, resp))
    return 0, PACKET_ID, None
