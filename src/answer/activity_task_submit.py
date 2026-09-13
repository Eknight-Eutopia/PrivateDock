import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .activity_task_helpers import (
    ACTIVITY_TASK_RESULT_FAILURE,
    ACTIVITY_TASK_RESULT_SUCCESS,
    load_activity_task_template,
    load_activity_task_id_set,
    build_award_drop_map,
    activity_drop_map_to_sorted_list,
)


def handle_submit_activity_task(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 20206
    payload = protobuf.CS_20205()
    payload.ParseFromString(buffer)

    response = protobuf.SC_20206(result=ACTIVITY_TASK_RESULT_FAILURE)
    act_id = payload.act_id
    task_ids = list(payload.task_ids)

    if act_id == 0 or not task_ids:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    try:
        activity_task_ids = load_activity_task_id_set(act_id)
    except Exception as e:
        return 0, packet_id, e

    templates = {}
    ordered_task_ids = []
    unique_task_ids = set()

    for task_id in task_ids:
        if task_id == 0:
            asyncio.create_task(client.send_message(packet_id, response))
            return 0, packet_id, None
        if task_id in unique_task_ids:
            continue
        if task_id not in activity_task_ids:
            asyncio.create_task(client.send_message(packet_id, response))
            return 0, packet_id, None
        try:
            template = load_activity_task_template(task_id)
        except Exception as e:
            return 0, packet_id, e
        unique_task_ids.add(task_id)
        templates[task_id] = template
        ordered_task_ids.append(task_id)

    drops = {}

    from src.orm.activity_task import try_submit_ready_commander_activity_task

    try:
        for task_id in ordered_task_ids:
            template = templates[task_id]
            submitted = try_submit_ready_commander_activity_task(
                client.commander.commander_id, act_id, task_id, template.get("target_num", 0)
            )
            if not submitted:
                asyncio.create_task(client.send_message(packet_id, response))
                return 0, packet_id, None

            task_drops = build_award_drop_map(template.get("award_display", []))
            for key, drop in task_drops.items():
                if key in drops:
                    drops[key]["number"] = drops[key].get("number", 0) + drop.get("number", 0)
                else:
                    drops[key] = drop

        response.result = ACTIVITY_TASK_RESULT_SUCCESS
    except Exception as e:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, e

    if hasattr(client.commander, "load"):
        try:
            client.commander.load()
        except Exception:
            pass

    award_list = activity_drop_map_to_sorted_list(drops)
    for item in award_list:
        entry = protobuf.DROPINFO()
        entry.type = item.get("type", 0)
        entry.id = item.get("id", 0)
        entry.number = item.get("number", 0)
        response.award_list.append(entry)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
