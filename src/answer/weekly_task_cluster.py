import json
from typing import Optional

from src.logger.logger import LOG_LEVEL_INFO
from src.connection.client import Client
from src.db.store import get_default_store
from src.orm.config_entry import afetch_config_entries_data, afetch_config_entry_data
from src.config.regions import MONDAY_0CLOCK_TIMESTAMPS
from src.region.region import current as current_region

WEEKLY_TASK_TEMPLATE_CATEGORY = "ShareCfg/weekly_task_template.json"
GAMESET_CATEGORY = "ShareCfg/gameset.json"


def _region_week_bucket(now_ts: int) -> int:
    """Monday-aligned week bucket matching the client's week anchor
    (monday_0oclock_timestamp). The client computes GetServerWeek from this
    anchor, so weekly resets must fall on Mondays, not the epoch (Thursday)
    boundary used by a naive now // 604800."""
    rid = current_region()
    anchor = MONDAY_0CLOCK_TIMESTAMPS.get(rid, 0)
    if anchor <= 0:
        return now_ts // 604800
    return (now_ts - anchor) // 604800


def _now_utc_ts() -> int:
    import datetime
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp())


def _tasks_to_map(tasks: list) -> dict:
    return {t["id"]: t for t in tasks}


def _map_to_tasks(task_map: dict) -> list:
    if not task_map:
        return []
    ids = sorted(task_map.keys())
    return [task_map[i] for i in ids]


def _next_weekly_task_template(templates: list, current: dict) -> tuple[Optional[dict], bool]:
    for candidate in templates:
        if candidate["target_num"] > current["target_num"]:
            return candidate, True
        if candidate["target_num"] == current["target_num"] and candidate["id"] > current["id"]:
            return candidate, True
    return None, False


def _to_weekly_task_proto(tasks: list) -> list:
    if not tasks:
        return []
    return [{"id": t["id"], "progress": t.get("progress", 0)} for t in tasks]


async def load_weekly_task_config() -> Optional[dict]:
    rows = await afetch_config_entries_data(WEEKLY_TASK_TEMPLATE_CATEGORY)
    if not rows:
        return None

    templates_by_id = {}
    templates_by_sub = {}
    for template in rows:
        if not isinstance(template, dict):
            continue
        tid = template.get("id")
        if tid is None:
            continue
        sub = template.get("sub_type", 0)
        templates_by_id[tid] = template
        if sub not in templates_by_sub:
            templates_by_sub[sub] = []
        templates_by_sub[sub].append(template)

    for sub in templates_by_sub:
        templates_by_sub[sub].sort(key=lambda t: (t.get("target_num", 0), t.get("id", 0)))

    weekly_target_entry = await afetch_config_entry_data(GAMESET_CATEGORY, 'weekly_target')
    weekly_drop_entry = await afetch_config_entry_data(GAMESET_CATEGORY, 'weekly_drop_client')

    targets = []
    drops = []
    if isinstance(weekly_target_entry, dict):
        desc = weekly_target_entry.get("description", [])
        if isinstance(desc, str):
            targets = json.loads(desc)
        else:
            targets = desc

    if isinstance(weekly_drop_entry, dict):
        desc = weekly_drop_entry.get("description", [])
        if isinstance(desc, str):
            drops = json.loads(desc)
        else:
            drops = desc

    return {
        "templates_by_id": templates_by_id,
        "templates_by_sub": templates_by_sub,
        "targets": targets,
        "drops": drops,
    }


def initial_weekly_tasks(config: dict) -> list:
    task_map = {}
    for _, templates in config["templates_by_sub"].items():
        if templates:
            template = templates[0]
            task_map[template["id"]] = {"id": template["id"], "progress": 0}
    return _map_to_tasks(task_map)


def ensure_weekly_tasks_initialized(state: dict, config: Optional[dict]) -> bool:
    if config is None or state.get("tasks"):
        return False
    state["tasks"] = initial_weekly_tasks(config)
    return True


async def handle_weekly_missions(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    config = await load_weekly_task_config()
    store = get_default_store()
    commander_id = client.commander.commander_id
    now = _now_utc_ts()

    response = protobuf.SC_20101()

    from src.orm.weekly_task_progress import aload_weekly_state, asave_weekly_state

    if store is not None:
        state_row = await aload_weekly_state(commander_id)
        week_bucket = _region_week_bucket(now)
        if state_row is None or state_row.get("week_start_unix") != week_bucket:
            tasks = []
            pt = 0
            reward_lv = 0
            if config is not None:
                tasks = initial_weekly_tasks(config)
            state = {"tasks": tasks, "counts": {}, "pt": pt, "reward_lv": reward_lv}
            await asave_weekly_state(commander_id, state, week_bucket)
        else:
            state = state_row

        info = protobuf.WEEKLY_INFO(pt=state.get("pt", 0), reward_lv=state.get("reward_lv", 0))
        for t in _to_weekly_task_proto(state.get("tasks", [])):
            wt = protobuf.WEEKLY_TASK_P20(id=t["id"], progress=t["progress"])
            info.task.append(wt)
        response.info.CopyFrom(info)
        from src.logger.logger import log_event
        log_event("Weekly", "Sending", f"SC_20101 commander={commander_id} tasks={len(info.task)} pt={info.pt} reward_lv={info.reward_lv}", LOG_LEVEL_INFO)

    from src.connection.server import generate_packet_header
    data = response.SerializeToString()
    header = generate_packet_header(20101, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 20101, None
