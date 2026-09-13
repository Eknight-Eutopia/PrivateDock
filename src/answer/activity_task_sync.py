from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf


def handle_activity_task_state_sync(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    init_tasks, info_tasks = _build_activity_task_sync_info(client.commander.commander_id)

    def _make_20201():
        r = protobuf.SC_20201()
        for t in init_tasks:
            ti = protobuf.TASKINFO(id=t["act_id"], progress=0)
            r.info.append(ti)
        return r

    def _make_202xx(tasks):
        r = protobuf.SC_20202()
        for t in tasks:
            ti = protobuf.TASKINFO(id=t["act_id"], progress=0)
            r.info.append(ti)
        return r

    for pid, msg in [(20201, _make_20201()), (20202, _make_202xx(info_tasks)), (20203, _make_202xx(info_tasks)), (20204, _make_202xx(info_tasks))]:
        data = msg.SerializeToString()
        header = generate_packet_header(pid, data, client.packet_index)
        client.write_to_buffer(header + data)
    return 0, 20204, None


def _build_activity_task_sync_info(commander_id: int) -> tuple:
    from src.orm.activity_task import list_commander_activity_tasks

    rows = list_commander_activity_tasks(commander_id)

    grouped = {}
    order = []

    for row in rows:
        act_id = row.get("act_id", 0) if isinstance(row, dict) else getattr(row, "act_id", 0)
        task_id = row.get("task_id", 0) if isinstance(row, dict) else getattr(row, "task_id", 0)
        progress = row.get("progress", 0) if isinstance(row, dict) else getattr(row, "progress", 0)
        submitted = row.get("submitted", False) if isinstance(row, dict) else getattr(row, "submitted", False)

        if act_id not in grouped:
            grouped[act_id] = {"tasks": [], "finish_ids": []}
            order.append(act_id)
        grouped[act_id]["tasks"].append({"id": task_id, "progress": progress})
        if submitted:
            grouped[act_id]["finish_ids"].append(task_id)

    init_tasks = []
    info_tasks = []
    for act_id in order:
        group = grouped[act_id]
        init_tasks.append({
            "act_id": act_id,
            "tasks": group["tasks"],
            "finish_ids": group["finish_ids"],
        })
        info_tasks.append({
            "act_id": act_id,
            "tasks": group["tasks"],
        })

    return init_tasks, info_tasks
