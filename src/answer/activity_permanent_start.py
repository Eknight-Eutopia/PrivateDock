import asyncio
from typing import Optional

from src.connection.client import Client
from src.connection.server import send_proto_message
from src.logger.logger import log_event, LOG_LEVEL_WARN
from src.protobuf import protobuf
def _gallery_task_ids(activity_id: int) -> list[int]:
    """Task ids (eliminate_task_id) of a Mini-Event Gallery (activity_task_permanent)
    entry. These are the real per-activity missions (35xxx) whose progress the
    client renders on the activity's sub-page; they advance through the normal
    emit_task_progress pipeline once accepted into commander_tasks."""
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        raw = get_config_entry("ShareCfg/activity_task_permanent.json", str(activity_id))
    except (NotFoundError, Exception):
        return []
    data = raw.data if hasattr(raw, "data") else raw
    if not isinstance(data, dict):
        return []
    raw_ids = data.get("eliminate_task_id") or []
    ids: list[int] = []
    if isinstance(raw_ids, list):
        for item in raw_ids:
            if isinstance(item, (int, float)):
                ids.append(int(item))
            elif isinstance(item, list):
                ids.extend(int(x) for x in item if isinstance(x, (int, float)))
    elif isinstance(raw_ids, (int, float)):
        ids.append(int(raw_ids))
    return sorted(set(ids))


def _seed_gallery_tasks(commander_id: int, activity_id: int, now: int) -> list[int]:
    """Accept ONLY day 1 of the activity's task groups (official gallery
    semantics: groups unlock one per calendar day from the personal start;
    further groups are accepted one per CS_11202 cmd=1 - see
    activity_operation._handle_task_list_sync). Idempotent for existing
    rows. Returns the task ids belonging to this activity (all groups, for
    state cleanup / task_list attachment)."""
    ids = _gallery_task_ids(activity_id)
    if not ids:
        return []
    from src.answer.activity_templates import load_activity_template
    from src.answer.activity_operation import _parse_task_groups
    template = load_activity_template(activity_id)
    groups = _parse_task_groups(template.config_data) if template else []
    day_one = groups[0] if groups else ids
    try:
        from src.db.store import get_default_store
        from src.answer.commandermisc.handlers import _seed_missing_tasks
        store = get_default_store()
        _seed_missing_tasks(commander_id, now, day_one)
    except Exception as e:
        log_event("Activities", "PermanentStart",
                  f"failed to seed gallery tasks for {activity_id}: {e}",
                  LOG_LEVEL_WARN)
    return ids


def _effective_gallery_day(commander_id: int, groups: list,

                           all_ids: list) -> int:
    """The day the sub-page should render NOW, computed from live rows rather
    than the persisted data3 (which can go stale if rows were edited by
    hand): the first group that is not fully claimed, clamped to groups that
    actually have rows or are day 1. Falls back to 1 when the run is fresh."""
    if not groups:
        return 1
    try:
        from src.db.store import get_default_store
        store = get_default_store()
        rows = store.fetch(
            "SELECT task_id, submit_time FROM commander_tasks "
            "WHERE commander_id=$1 AND task_id=ANY($2)",
            commander_id, all_ids,
        )
        claimed = {int(r[0]) for r in rows if int(r[1] or 0) > 0}
        for idx, group in enumerate(groups):
            if not all(t in claimed for t in group):
                return idx + 1
        return len(groups)
    except Exception:
        return 1


def _fill_task_list(info: dict, commander_id: int, task_ids: list[int]) -> None:
    """Attach live commander_tasks rows so the pushed ACTIVITYINFO carries the
    current progress (the client's Activity VO task_list)."""
    if not task_ids:
        return
    try:
        from src.orm.commander_task import fetch_commander_tasks
        rows = fetch_commander_tasks(commander_id, task_ids)
        info["task_list"] = [
            {"id": r.task_id, "progress": r.progress, "accept_time": r.accept_time, "submit_time": r.submit_time}
            for r in rows
        ]
    except Exception as e:
        log_event("Activities", "PermanentStart",
                  f"failed to load task rows for {task_ids}: {e}",
                  LOG_LEVEL_WARN)


def _push_task_sync_20003(client: Client, commander_id: int, task_ids: list[int]) -> None:
    """Push the day's freshly-accepted commander_tasks rows as SC_20003.

    The client's TaskProxy adds activity-task VOs from SC_20003 (addActData,
    setActId) - this is also how the OFFICIAL server delivers a gallery day's
    tasks (capture 2026-09-05, activity 6021: SC_20003 with the day's two
    tasks right after CS_11202). SC_20001 (initTaskInfo) sets no act id, so
    it is the wrong channel for activity tasks. The ACTIVITYINFO.task_list
    embedded in the SC_11201 push is ignored by the client's Activity VO."""
    if not task_ids:
        return
    try:
        from src.orm.commander_task import fetch_commander_tasks
        rows = fetch_commander_tasks(commander_id, task_ids)
        if not rows:
            return
        sync = protobuf.SC_20003()
        for r in rows:
            sync.info.append(protobuf.TASK_ADD(
                id=r.task_id, progress=r.progress,
                accept_time=r.accept_time, submit_time=r.submit_time))
        asyncio.create_task(send_proto_message(20003, client, sync))
    except Exception as e:
        log_event("Activities", "PermanentStart",
                  f"failed to push task sync for {task_ids}: {e}",
                  LOG_LEVEL_WARN)



def handle_activity_permanent_start(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11206()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11207, e

    activity_id = payload.activity_id
    response = protobuf.SC_11207(result=1)

    if activity_id == 0:
        asyncio.create_task(send_proto_message(11207, client, response))
        return 0, 11207, None

    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        get_config_entry("ShareCfg/activity_task_permanent.json", str(activity_id))
    except (NotFoundError, Exception):
        asyncio.create_task(send_proto_message(11207, client, response))
        return 0, 11207, None

    from src.orm.activity_permanent_state import get_or_create_activity_permanent_state
    try:
        state_orm = get_or_create_activity_permanent_state(client.commander.commander_id)
        state = {c.name: getattr(state_orm, c.name) for c in state_orm.__table__.columns}
    except Exception as e:
        return 0, 11207, e

    finished_ids = [int(x) for x in state.get("finished_activity_ids", [])]
    if activity_id in finished_ids:
        asyncio.create_task(send_proto_message(11207, client, response))
        return 0, 11207, None

    current_id = int(state.get("current_activity_id", 0))
    if current_id != 0 and current_id != activity_id:
        asyncio.create_task(send_proto_message(11207, client, response))
        return 0, 11207, None

    if current_id != activity_id:
        from src.orm.activity_permanent_state import get_or_create_activity_permanent_state as _get_state_orm
        state_orm2 = _get_state_orm(client.commander.commander_id)
        state_orm2.current_activity_id = activity_id
        from src.orm.activity_permanent_state import save_activity_permanent_state
        try:
            save_activity_permanent_state(state_orm2)
        except Exception as e:
            return 0, 11207, e

    from src.answer.activity_templates import load_activity_template
    from src.answer.activity_builders import build_activity_info, activity_stop_time

    template = load_activity_template(activity_id)
    if template is None:
        return 0, 11207, Exception(f"activity template {activity_id} not found")

    stop_time = activity_stop_time(template.time)
    info = build_activity_info(template, stop_time)
    if info is None:
        asyncio.create_task(send_proto_message(11207, client, response))
        return 0, 11207, None

    import time as _time
    commander_id = client.commander.commander_id
    now = int(_time.time())
    task_ids = _seed_gallery_tasks(commander_id, activity_id, now)

    from src.answer.activity_templates import load_activity_template as _lt
    from src.answer.activity_operation import _parse_task_groups as _ptg
    _tpl = _lt(activity_id)
    _groups = _ptg(_tpl.config_data) if _tpl else []
    # Effective day comes from LIVE rows (first not-fully-claimed group), not
    # from the persisted data3: a hand-edited DB (deleted tasks, wiped state)
    # can leave data3 pointing at a group that has no rows, and the day push
    # would then be silently skipped (no rows -> no SC_20003) leaving the
    # client without its day's TaskProxy VOs - the exact observed cmd=1 loop.
    day = _effective_gallery_day(commander_id, _groups, task_ids)
    _day_ids = _groups[day - 1] if _groups and 1 <= day <= len(_groups) else task_ids
    if not _day_ids:
        _day_ids = task_ids

    # Stamp the personal start anchor (data2 = day-1 accept time) so the
    # calendar day gate in activity_operation._unlocked_day counts from the
    # run's real start; persist the effective day (data3).
    try:
        from src.orm.activity_store_state import (
            get_activity_store_data2_sync,
            set_activity_store_day_state_sync,
        )
        anchor = get_activity_store_data2_sync(commander_id, activity_id)
        if anchor <= 0:
            anchor = now
        set_activity_store_day_state_sync(commander_id, activity_id, anchor, day, update_anchor=True)
    except Exception as e:
        log_event("Activities", "PermanentStart",
                  f"failed to persist day state for {activity_id}: {e}",
                  LOG_LEVEL_WARN)
    # Push the day's rows (the client's TaskProxy learns them via addActData
    # on SC_20003, exactly like the official server's handout).
    _push_task_sync_20003(client, commander_id, _day_ids)
    # data3 = the day the sub-page renders (config_data[data3]); default 1 so
    # day 1 renders immediately after starting instead of a blank list.
    info["data3"] = day
    _fill_task_list(info, commander_id, _day_ids)

    # The client decodes SC_11201 as a protobuf ACTIVITYINFO (ActivityProxy
    # on(11201) -> Activity.Create) - a JSON dict here silently breaks the
    # push and the selected activity never lands in ActivityProxy.
    from src.answer.activities import _info_to_proto
    push = protobuf.SC_11201(activity_info=_info_to_proto(info))
    asyncio.create_task(send_proto_message(11201, client, push))

    response.result = 0
    asyncio.create_task(send_proto_message(11207, client, response))
    return 0, 11207, None
