import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.db.store import get_default_store
from src.orm.commander_task import (
    create_or_accept_task,
    fetch_commander_tasks,
    fetch_commander_task_progress_map,
    get_commander_task_submit_time,
)
from src.orm.config_entry import get_config_entry
from src.protobuf import protobuf

from .activity_constants import (
    ACTIVITY_TYPE_EVENT_SINGLE,
    ACTIVITY_TYPE_FRESH_TEC_CATCHUP,
    ACTIVITY_CMD_SINGLE_EVENT_REFRESH,
    ACTIVITY_TYPE_TASK_LIST,
    ACTIVITY_TYPE_TASK_RES,
    ACTIVITY_TYPE_STORY_AWARD,
    ACTIVITY_TYPE_MINGSHI,
)


def handle_activity_operation(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 11203
    payload = protobuf.CS_11202()
    payload.ParseFromString(buffer)

    activity_id = payload.activity_id
    cmd = payload.cmd
    arg1 = payload.arg1
    arg2 = payload.arg2
    arg3 = payload.arg3

    # Wishing Well (PrayPool): activity_id comes from activity_ship_create and is
    # not a normal activity_template entry. Route before the template lookup.
    from .shipbuild.wishing_well import get_wishing_well_activity_ids, handle_wishing_well
    if activity_id in get_wishing_well_activity_ids():
        from src.logger.logger import log_event, LOG_LEVEL_DEBUG
        log_event("WishingWell", "Debug", f"routing activity_id={activity_id} cmd={cmd}", LOG_LEVEL_DEBUG)
        return handle_wishing_well(payload, client)

    from .activity_templates import load_activity_template
    try:
        template = load_activity_template(activity_id)
    except Exception as e:
        return 0, packet_id, e

    if template is None:
        return _handle_activity_operation_noop(client)
    if template.type == ACTIVITY_TYPE_FRESH_TEC_CATCHUP:
        return _handle_tec_catchup(template, client, cmd=cmd, arg1=arg1)
    if template.type in (ACTIVITY_TYPE_TASK_LIST, ACTIVITY_TYPE_TASK_RES):
        # Mini-Event Gallery / per-day skin events (type 18 TASK_LIST) and the
        # TASK_RES variant: the page gates itself on the activity's tasks being
        # received (updateActivityTaskStatus), so an empty SC_11203 makes the
        # client re-send CS_11202 forever. Accept/sync the tasks instead.
        return _handle_task_list_sync(template, client, cmd=cmd, arg1=arg1)
    if template.type == ACTIVITY_TYPE_EVENT_SINGLE:
        if cmd != ACTIVITY_CMD_SINGLE_EVENT_REFRESH:
            return 0, packet_id, ValueError(f"unsupported single event cmd: {cmd}")
        return _handle_single_event_refresh(template.config_data, client)
    if template.type == ACTIVITY_TYPE_STORY_AWARD:
        # StoryAwardPage ("Stage Reward"): per-stage clear rewards claimed with
        # cmd=1 arg1=chapter_id. Any other cmd has no meaning for this type.
        if cmd != 1 or arg1 <= 0:
            return _handle_activity_operation_noop(client)
        return _handle_story_award_claim(template, client, chapter_id=arg1)
    if template.type == ACTIVITY_TYPE_MINGSHI:
        # Akashi's Commission chain (activity 21): cmd=1 hands out the next
        # commission task (sent after the 30 hidden shop taps), cmd=2
        # arg1=flag_id records one hidden touch flag (+1 progress).
        return _handle_mingshi_commission(template, client, cmd=cmd, arg1=arg1)
    elif template.type in (1, 4):
        return _handle_level_award_claim(template, client, threshold=arg1)
    elif template.type == 3:
        return _handle_7dayslogin_claim(template, client)
    elif template.type == 6:
        return _handle_monthsign_claim(template, client, cmd=cmd, resign_day=arg1)
    else:
        return _handle_activity_operation_noop(client)


def _handle_activity_operation_noop(client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 11203
    response = protobuf.SC_11203(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


_TEC_CATCHUP_PHASES_CACHE: Optional[list] = None


def _tec_catchup_phases(template) -> list:
    """Phase table from activity_template.config_data[2]: each phase is
    [task_id_list, finish_task_id]. Lua reads config_data[3] (1-indexed)."""
    global _TEC_CATCHUP_PHASES_CACHE
    if _TEC_CATCHUP_PHASES_CACHE is not None:
        return _TEC_CATCHUP_PHASES_CACHE
    phases = []
    cd = template.config_data
    if isinstance(cd, list) and len(cd) > 2 and isinstance(cd[2], list):
        for phase in cd[2]:
            if isinstance(phase, list) and phase and isinstance(phase[0], list):
                finish = int(phase[1]) if len(phase) > 1 else 0
                phases.append(([int(t) for t in phase[0]], finish))
    _TEC_CATCHUP_PHASES_CACHE = phases
    return phases


def _handle_tec_catchup(template, client, cmd: int, arg1: int) -> tuple[int, int, Optional[Exception]]:
    """Fresh Tech Catchup (Training Camp / Dev Missions) CS_11202 ops.

    Client model (trainingcampscene.setTechPhrase + ActivityOperationCommand
    ACTIVITY_TYPE_FRESH_TEC_CATCHUP branch):
      data1      = current phase id (fresh default 1; phaseId 0 until started)
      data2      = 1 once the first phase has been started via cmd=3
      data1_list = ids of COMPLETED phases
    cmds: 3 = start phase 1; 1 arg1=N = complete current phase, move to N;
    2 = client auto-ack when all of a phase's sub-tasks reached target.
    The client mirrors these state changes locally on SC_11203 success, so the
    server's job is to validate + persist so SC_11200 restores it next login."""
    packet_id = 11203
    store = get_default_store()
    if store is None:
        return _handle_activity_operation_noop(client)

    commander_id = client.commander.commander_id

    def _send(result: int):
        response = protobuf.SC_11203(result=result)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    row = store.fetchrow(
        "SELECT data1, data2, data1_list FROM activity_store_states "
        "WHERE commander_id = $1 AND activity_id = $2",
        commander_id, template.id,
    )
    try:
        data1 = int(row[0] or 0) if row else 0
        data2 = int(row[1] or 0) if row else 0
        done = [int(x) for x in (json.loads(row[2]) if row else []) or []]
    except Exception:
        data1, data2, done = 0, 0, []
    if data1 <= 0:
        data1 = 1

    phases = _tec_catchup_phases(template)

    if cmd == 3:
        # Start Series 1. Idempotent: only meaningful before the first start.
        data1, data2 = 1, 1
    elif cmd == 1:
        target = int(arg1 or 0)
        if target <= 0 or target > len(phases):
            return _send(1)
        if target == data1:
            # Idempotent re-request (client quirk: the pre-start tab's Unlock
            # button sends arg1 == current phase). Success, nothing to change.
            return _send(0)
        if target != data1 + 1:
            return _send(1)
        # Genuine progression gate: every sub-task of the current phase must have
        # reached its target_num before the next series unlocks.
        subs, _finish = phases[data1 - 1]
        prog = fetch_commander_task_progress_map(commander_id, subs)
        from .task_handlers import _load_task_template
        for tid in subs:
            tpl = _load_task_template(tid)
            tnum = int((tpl or {}).get("target_num", 0) or 0) or 1
            if prog.get(tid, 0) < tnum:
                return _send(1)
        if data1 not in done:
            done.append(data1)
        data1 = target
        data2 = 1
    elif cmd == 2:
        pass
    else:
        return _send(1)

    store.execute(
        "INSERT INTO activity_store_states (commander_id, activity_id, data1, data2, data3, data1_list) "
        "VALUES ($1, $2, $3, $4, 0, $5) "
        "ON CONFLICT (commander_id, activity_id) "
        "DO UPDATE SET data1 = $3, data2 = $4, data1_list = $5",
        commander_id, template.id, data1, data2, json.dumps(done),
    )
    return _send(0)


def _handle_single_event_refresh(config_data: list, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 11203
    ids = _parse_activity_config_ids(config_data)

    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError

    daily_ids = []
    for _id in ids:
        try:
            entry = get_config_entry("ShareCfg/activity_single_event.json", str(_id))
            config = json.loads(entry.data) if isinstance(entry.data, str) else entry.data
            if config.get("type") == 2:
                daily_ids.append(_id)
        except NotFoundError:
            continue
        except Exception:
            continue

    response = protobuf.SC_11203(result=0)
    response.number.extend(daily_ids)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _load_level_award_entry(config_id: str):
    entry = get_config_entry("ShareCfg/activity_level_award.json", config_id)
    if entry is not None:
        return entry
    from src.orm.config_entry import list_config_entries
    entries = list_config_entries("ShareCfg/activity_level_award.json")
    if entries:
        return entries[0]
    return None


def _handle_level_award_claim(template, client: Client, threshold: int = 0) -> tuple[int, int, Optional[Exception]]:
    packet_id = 11203
    store = get_default_store()
    if store is None:
        return _handle_activity_operation_noop(client)

    config_id = str(template.config_id)
    entry = _load_level_award_entry(config_id)
    if entry is None:
        return _handle_activity_operation_noop(client)

    award_data = json.loads(entry.data) if isinstance(entry.data, str) else entry.data
    front_drops = award_data.get("front_drops", []) if isinstance(award_data, dict) else []

    commander_id = client.commander.commander_id
    level_row = store.fetchrow("SELECT level FROM commanders WHERE commander_id = $1", commander_id)
    level = level_row[0] if level_row else 1
    activity_id = template.id

    claimed_level = 0
    row = store.fetchrow(
        "SELECT data1 FROM activity_store_states WHERE commander_id = $1 AND activity_id = $2",
        commander_id, activity_id,
    )
    if row:
        claimed_level = row[0] if row[0] else 0

    if threshold == 0:
        response = protobuf.SC_11203(result=0)
        for entry_data in front_drops:
            if not isinstance(entry_data, list) or len(entry_data) < 2:
                continue
            t = entry_data[0]
            if isinstance(t, (int, float)):
                t = int(t)
                if t > claimed_level and t <= level:
                    response.number.append(t)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    merged = {}
    new_claimed = claimed_level
    for entry_data in front_drops:
        if not isinstance(entry_data, list) or len(entry_data) < 2:
            continue
        t = entry_data[0]
        if not isinstance(t, (int, float)):
            continue
        t = int(t)
        if t != threshold:
            continue
        if t <= claimed_level or t > level:
            break
        new_claimed = max(new_claimed, t)
        for drop in entry_data[1:]:
            if isinstance(drop, list) and len(drop) >= 3:
                key = f"{drop[0]}_{drop[1]}"
                if key in merged:
                    merged[key]["number"] += int(drop[2])
                else:
                    merged[key] = {"type": int(drop[0]), "id": int(drop[1]), "number": int(drop[2])}
        break

    if not merged:
        return _handle_activity_operation_noop(client)

    store.execute(
        "INSERT INTO activity_store_states (commander_id, activity_id, data1, str_data1, created_at, updated_at) "
        "VALUES ($1, $2, $3, '', NOW(), NOW()) "
        "ON CONFLICT (commander_id, activity_id) DO UPDATE SET data1 = $3, updated_at = NOW()",
        commander_id, activity_id, new_claimed,
    )

    for key in sorted(merged.keys()):
        d = merged[key]
        if d["type"] == 1:
            from src.orm.resource import add_resource
            add_resource(commander_id, d["id"], d["number"])
        elif d["type"] == 2:
            from src.orm.item import add_item
            add_item(commander_id, d["id"], d["number"])
        elif d["type"] == 4:
            # Ship grants go through the single creation path
            # (client.commander.add_ship -> owned_ship.add_ship): GLOBAL id
            # allocation, auto-lock, default equipment slots, in-memory cache
            # update. The previous inline INSERT used per-owner MAX(id) —
            # owned_ships.id is a GLOBAL primary key, so a second commander
            # would collide on id=1 — and granted only one ship regardless
            # of d["number"].
            for _ in range(max(1, d["number"])):
                client.commander.add_ship(d["id"])

    response = protobuf.SC_11203(result=0)
    for key in sorted(merged.keys()):
        d = merged[key]
        response.award_list.append(protobuf.DROPINFO(type=d["type"], id=d["id"], number=d["number"]))
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _handle_story_award_claim(
    template, client: Client, chapter_id: int = 0
) -> tuple[int, int, Optional[Exception]]:
    """StoryAwardPage (type 59, "Stage Reward") CS_11202 cmd=1 arg1=chapter_id.

    Config: ShareCfg/activity_event_chapter_award.json[config_id] ->
    {chapter: [stage ids], award_display: [[[type,id,count], ...], ...]} with
    award_display[i] aligned to chapter[i]. The client gates the Get button on
    its OWN chapter-clear mirror and, on result=0, appends arg1 to the
    activity's data1_list itself — so the server must persist data1_list
    (SC_11200 stamps it back on login) or the reward re-opens after re-login
    while nothing was granted."""
    packet_id = 11203
    store = get_default_store()
    if store is None or chapter_id <= 0:
        return _handle_activity_operation_noop(client)

    from .activity_sign import load_store_state, save_store_state, grant_drop_list

    commander_id = client.commander.commander_id
    activity_id = template.id

    try:
        raw = get_config_entry("ShareCfg/activity_event_chapter_award.json", str(template.config_id))
    except Exception:
        raw = None
    config = raw.data if raw is not None else None
    if not isinstance(config, dict):
        return _handle_activity_operation_noop(client)

    chapters = config.get("chapter") or []
    try:
        idx = [int(c) for c in chapters].index(int(chapter_id))
    except (ValueError, TypeError):
        return _handle_activity_operation_noop(client)

    state = load_store_state(commander_id, activity_id) or {}
    claimed = [int(x) for x in (state.get("data1_list") or []) if isinstance(x, (int, float))]
    if chapter_id in claimed:
        return _handle_activity_operation_noop(client)

    # Gate on the server's own clear state: chapter_progress.pass_count >= 1
    # means the stage was cleared at least once (battle path records it).
    from .task_handlers import _chapter_progress_state
    progress = _chapter_progress_state(commander_id)
    if int((progress.get(chapter_id) or {}).get("pass", 0)) < 1:
        return _handle_activity_operation_noop(client)

    award_display = config.get("award_display") or []
    drops = award_display[idx] if idx < len(award_display) else []
    drops = [d for d in (drops or []) if isinstance(d, (list, tuple)) and len(d) >= 3]
    if not drops:
        return _handle_activity_operation_noop(client)

    award_list = grant_drop_list(commander_id, [list(d) for d in drops])

    save_store_state(
        commander_id, activity_id,
        data1=state.get("data1") or 0,
        data2=state.get("data2") or 0,
        data3=state.get("data3") or 0,
        day_list=claimed + [chapter_id],
        str_data1=state.get("str_data1") if isinstance(state.get("str_data1"), str) else "",
    )

    response = protobuf.SC_11203(result=0)
    for drop in award_list:
        response.award_list.append(drop)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _handle_mingshi_commission(
    template, client: Client, cmd: int = 1, arg1: int = 0
) -> tuple[int, int, Optional[Exception]]:
    """Akashi's Commission chain (activity 21, type 17, config_id 5001).

    Client flow (clickmingshicommand.lua + taskproxy.lua):
      - 30 taps on Akashi in the Charge/Shop screen (client-side trigger,
        task_data_trigger[1]) send CS_11202 cmd=1 while no commission task VO
        exists. The server must ACCEPT the current chain task so it appears
        in TaskProxy (the client never advances next_task itself, so the
        chain position is server-side).
      - cmd=2 arg1=flag_id comes from the hidden touch flags (shop stamp etc.),
        once per flag while the touch-flag commission (config_data[0], Lua
        config_data[1]) is in progress: append to data1_list and give +1
        progress to that task. data1_list is stamped back by SC_11200 so
        flags cannot re-fire after re-login.
    """
    packet_id = 11203
    store = get_default_store()
    if store is None:
        return _handle_activity_operation_noop(client)

    if cmd == 2:
        return _handle_mingshi_touch_flag(template, client, flag_id=arg1)
    if cmd != 1:
        return _handle_activity_operation_noop(client)

    from .task_handlers import _load_task_template

    commander_id = client.commander.commander_id
    import time as _time
    now = int(_time.time())

    def _next_task(tid: int) -> int:
        tpl = _load_task_template(tid) or {}
        try:
            return int(tpl.get("next_task", 0) or 0)
        except (TypeError, ValueError):
            return 0

    # Walk the chain and accept the first task that has no row yet, stopping at
    # a task already in progress (a submitted task means the chain moved on).
    tid = int(template.config_id or 0)
    seen = set()
    while tid > 0 and tid not in seen:
        seen.add(tid)
        submit_time = get_commander_task_submit_time(commander_id, tid)
        if submit_time is None:
            if _load_task_template(tid) is None:
                break
            create_or_accept_task(commander_id, tid, now)
            from src.answer.commandermisc.handlers import _push_task_add
            _push_task_add(client, tid, 0, now)
            break
        if not submit_time:
            break  # already accepted, in progress
        # Claimed link -> keep walking: the walk starts at the chain head every
        # time, so passing the claimed prefix is how the chain position is found.
        tid = _next_task(tid)

    response = protobuf.SC_11203(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _handle_mingshi_touch_flag(
    template, client: Client, flag_id: int = 0
) -> tuple[int, int, Optional[Exception]]:
    """Hidden touch flags (cmd=2 arg1=flag_id): persist to data1_list and add
    +1 progress to the touch-flag commission task (config_data[0])."""
    packet_id = 11203
    store = get_default_store()
    if store is None or int(flag_id or 0) <= 0:
        return _handle_activity_operation_noop(client)

    from .activity_sign import load_store_state, save_store_state
    from .task_handlers import _load_task_template

    commander_id = client.commander.commander_id
    flag = int(flag_id)

    state = load_store_state(commander_id, template.id) or {}
    flags = [int(x) for x in (state.get("data1_list") or [])
             if isinstance(x, (int, float))]
    if flag in flags:
        return _handle_activity_operation_noop(client)
    flags.append(flag)

    cd = template.config_data
    touch_task = 0
    if isinstance(cd, list) and cd and isinstance(cd[0], (int, float)):
        touch_task = int(cd[0])

    progress = 0
    if touch_task > 0:
        tpl = _load_task_template(touch_task) or {}
        tnum = int(tpl.get("target_num", 0) or 0) or 1
        try:
            store.execute(
                "UPDATE commander_tasks SET progress = LEAST(progress + 1, $3) "
                "WHERE commander_id = $1 AND task_id = $2 AND submit_time = 0",
                commander_id, touch_task, tnum,
            )
            row = store.fetchrow(
                "SELECT progress FROM commander_tasks WHERE commander_id = $1 AND task_id = $2",
                commander_id, touch_task,
            )
            progress = int(row[0] or 0) if row else 0
        except Exception:
            progress = 0
        if progress:
            push = protobuf.SC_20002()
            push.info.append(protobuf.TASK_PROGRESS(id=touch_task, progress=progress))
            asyncio.create_task(client.send_message(20002, push))

    save_store_state(
        commander_id, template.id,
        data1=state.get("data1") or 0,
        data2=state.get("data2") or 0,
        data3=state.get("data3") or 0,
        day_list=flags,
        str_data1=state.get("str_data1") if isinstance(state.get("str_data1"), str) else "",
    )

    response = protobuf.SC_11203(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _parse_json_uint(value) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _parse_activity_config_ids(config_data) -> list:
    if isinstance(config_data, list):
        ids = []
        for value in config_data:
            num = _parse_json_uint(value)
            if num is not None:
                ids.append(num)
        return ids
    return []


def _handle_7dayslogin_claim(template, client: Client) -> tuple[int, int, Optional[Exception]]:
    """7dayslogin (type 3) CS_11202 cmd=1 claim.

    Client readyToAchieve: data1 < #front_drops and not IsSameDay(now, data2)
    and data2 < now. On success client increments data1 and sets data2 = now.
    """
    packet_id = 11203
    from .activity_sign import (
        load_7day_config,
        load_store_state,
        save_store_state,
        grant_drop_list,
        is_same_day,
        _now_unix,
    )

    store = get_default_store()
    if store is None:
        return _handle_activity_operation_noop(client)

    commander_id = client.commander.commander_id
    activity_id = template.id
    config = load_7day_config(template.config_id)
    if config is None:
        return _handle_activity_operation_noop(client)

    front_drops = config.get("front_drops", []) if isinstance(config, dict) else []
    if not front_drops:
        return _handle_activity_operation_noop(client)

    state = load_store_state(commander_id, activity_id) or {}
    claimed = state.get("data1") or 0
    last_claim = state.get("data2") or 0
    now = _now_unix()

    if claimed >= len(front_drops) or is_same_day(now, last_claim) or last_claim >= now:
        return _handle_activity_operation_noop(client)

    day_drop = front_drops[claimed]
    drops = [day_drop] if isinstance(day_drop, list) and len(day_drop) >= 3 else []

    save_store_state(commander_id, activity_id, data1=claimed + 1, data2=now)

    response = protobuf.SC_11203(result=0)
    award_list = grant_drop_list(commander_id, drops)
    for drop in award_list:
        response.award_list.append(drop)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _handle_monthsign_claim(
    template, client: Client, cmd: int = 1, resign_day: int = 0
) -> tuple[int, int, Optional[Exception]]:
    """Monthsign (type 6) CS_11202 claim.

    Rewards are sequential per the wiki ("claim the earliest, unclaimed
    reward... limited to one reward per day... start over from Day 1"): the
    Nth claim of the month grants config["day"..N], regardless of the
    calendar day. data1_list stores the actual calendar days signed in on
    (matching the client's local update), so len(data1_list) is the number of
    rewards claimed and `today not in data1_list` gates one claim per day.

    cmd=1: normal claim. cmd=3: re-sign a missed day (arg1 = day).
    Client findNextAutoActivity: when year/month differ, resets data1=year,
    data2=month, data1_list={} and claims; otherwise claims when today is not
    in data1_list; re-signs when day > #data1_list and data3 < resign_count.
    """
    packet_id = 11203
    from .activity_sign import (
        load_month_sign_config,
        load_store_state,
        save_store_state,
        grant_drop_list,
        current_day,
        current_month_id,
        _now_unix,
    )

    store = get_default_store()
    if store is None:
        return _handle_activity_operation_noop(client)

    commander_id = client.commander.commander_id
    activity_id = template.id
    now = _now_unix()
    year, month = current_month_id(now)

    state = load_store_state(commander_id, activity_id) or {}
    state_year = state.get("data1") or 0
    state_month = state.get("data2") or 0
    state_data3 = state.get("data3") or 0
    day_list = list(state.get("data1_list") or [])

    # New month/year: reset claimed days.
    if state_year != year or state_month != month:
        day_list = []
        state_data3 = 0

    config = load_month_sign_config(month)
    if config is None:
        return _handle_activity_operation_noop(client)

    resign_count = config.get("resign_count", 0) if isinstance(config, dict) else 0

    if cmd == 3:
        day = int(resign_day)
        # Re-sign only a missed day not already claimed and not today/future.
        if day <= 0 or day in day_list:
            return _handle_activity_operation_noop(client)
        today = current_day(now)
        if day >= today or state_data3 >= (resign_count or 0):
            return _handle_activity_operation_noop(client)
        reward_day = day
    else:
        day = current_day(now)
        # One claim per calendar day (client gate: today not in data1_list).
        if day in day_list:
            return _handle_activity_operation_noop(client)
        # Rewards are sequential, not calendar-day bound: the Nth claim of the
        # month grants config["day"..N]. data1_list stores the actual calendar
        # days signed in on, so its length is the number of rewards claimed.
        reward_day = len(day_list) + 1

    from .activity_sign import parse_day_drop
    drops = parse_day_drop(config, reward_day)
    if not drops:
        return _handle_activity_operation_noop(client)

    day_list.append(day)
    day_list.sort()
    if cmd == 3:
        state_data3 += 1

    save_store_state(
        commander_id,
        activity_id,
        data1=year,
        data2=month,
        data3=state_data3,
        day_list=day_list,
    )

    response = protobuf.SC_11203(result=0)
    award_list = grant_drop_list(commander_id, drops)
    for drop in award_list:
        response.award_list.append(drop)

    # Monthsign milestone rewards (front_drops: [day, type, id, count]) are
    # granted automatically when the month's claimed-day count reaches the
    # milestone threshold. The client has no separate claim flow for them.
    milestones = config.get("front_drops", []) if isinstance(config, dict) else []
    for milestone in milestones or []:
        if not isinstance(milestone, list) or len(milestone) < 4:
            continue
        threshold = int(milestone[0])
        if len(day_list) != threshold:
            continue
        milestone_drop = [int(milestone[1]), int(milestone[2]), int(milestone[3])]
        milestone_awards = grant_drop_list(commander_id, [milestone_drop])
        for drop in milestone_awards:
            response.award_list.append(drop)
        break

    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _parse_task_groups(config_data) -> list:
    """activity_template.config_data for type 18 (TASK_LIST) / 40 (TASK_RES):
    a list of task groups - each group is the set of task ids of one "day" of
    the activity. Tolerates JSON-text storage and flat id lists."""
    try:
        data = json.loads(config_data) if isinstance(config_data, str) else config_data
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    groups = []
    for group in data:
        if isinstance(group, (int, float)):
            groups.append([int(group)])
        elif isinstance(group, list):
            ids = []
            for item in group:
                if isinstance(item, (int, float)):
                    ids.append(int(item))
            if ids:
                groups.append(ids)
    return groups


def _unlocked_day( commander_id: int, activity_id: int, groups: list,

                  now: int) -> int:
    """Highest day (1-based group index) the player may currently be served,
    gated by one group per REGIONAL calendar day since the personal start.

    The anchor lives in activity_store_states.data2 (the day-1 task accept
    time; 0 = no run yet -> day 1). This mirrors the official server:
    the day counter advances by the calendar, NOT by task completion -
    a returning player catches up one missed group per CS_11202 cmd=1,
    and can never receive more groups than days elapsed
    ("Takes at least N days to complete")."""
    anchor = 0
    try:
        from src.orm.activity_store_state import get_activity_store_data2_sync
        anchor = get_activity_store_data2_sync(commander_id, activity_id)
    except Exception:
        anchor = 0
    if anchor <= 0:
        return 1
    from src.region.region import offset as _region_offset
    day_secs = 86400
    local_day = lambda ts: (ts + _region_offset()) // day_secs
    elapsed = local_day(now) - local_day(anchor) + 1
    return max(1, min(len(groups), elapsed))


def _handle_task_list_sync(
    template, client: Client, cmd: int = 1, arg1: int = 0
) -> tuple[int, int, Optional[Exception]]:
    """CS_11202 for TASK_LIST (type 18) / TASK_RES (type 40) activities.

    Original semantics: the day counter advances by the calendar from the player's
    personal start, NOT by task completion. On cmd=1 the server accepts at
    most ONE not-yet-accepted group of tasks (the earliest unlocked one) and
    pushes exactly those rows via SC_20003; the SC_11203 reply itself carries
    only result: 0. The client re-requests cmd=1 after each group is fully
    claimed (or when its day's task VOs are missing), catching up missed
    days one group per request. Mass-accepting every group up front instead
    left the client with nothing to request, so the day (data3) never
    advanced and the sub-page was stuck on an old day (owner-observed on
    activity 6002 "Angel or Devil in White?" at day 2/7).

    ``data3`` (the day the sub-page renders from config_data[data3]) is
    recomputed as the day of the earliest not-fully-claimed group and
    persisted in activity_store_states, so SC_11200/SC_11201 restore it."""
    from src.logger.logger import log_event, LOG_LEVEL_DEBUG
    packet_id = 11203
    store = get_default_store()
    if store is None:
        return _handle_activity_operation_noop(client)

    commander_id = client.commander.commander_id
    groups = _parse_task_groups(template.config_data)
    ordered: list[int] = []
    for group in groups:
        for tid in group:
            if tid not in ordered:
                ordered.append(tid)
    if not ordered:
        return _handle_activity_operation_noop(client)

    import time as _time
    now = int(_time.time())

    from .task_handlers import _load_task_template
    valid_set = {tid for tid in ordered if _load_task_template(tid) is not None}
    if not valid_set:
        return _handle_activity_operation_noop(client)

    unlocked = _unlocked_day(commander_id, template.id, groups, now)

    # Live rows only for ALREADY-ACCEPTED tasks; unaccepted groups must NOT
    # be seeded here (that is the day gate itself).
    rows = []
    try:
        rows = fetch_commander_tasks(commander_id, sorted(valid_set))
    except Exception:
        rows = []
    accepted = {r.task_id for r in rows}
    claimed = {r.task_id for r in rows if r.submit_time > 0}

    # Accept the next group when it is fresh (no accepted task) AND every
    # earlier group is fully claimed AND it is calendar-unlocked. Capture
    # 2026-09-05 (activity 6021): each handout of day N+1 followed the CS_20005
    # claims of BOTH day-N tasks (35264/35265 -> day 5, 35266/35267 -> day 6,
    # 35268/35269 -> day 7) - originally never grants a group while the
    # previous one is unfinished, even inside the unlocked window. A group
    # that is already accepted but not fully claimed stays the "current" day
    # (data3) and gates the next handout.
    newly: list[int] = []
    current_day_ids: list[int] = []  # the day's rows to (re)push, if any are missing
    if cmd == 1:
        for idx, group in enumerate(groups):
            gday = idx + 1
            if gday > unlocked:
                break
            gids = [t for t in group if t in valid_set]
            if not gids:
                continue
            if all(t in claimed for t in gids):
                continue  # day finished - the next group may follow
            # first unfinished group
            if not any(t in accepted for t in gids):
                newly = gids
            else:
                current_day_ids = gids
            break

    if newly:
        from src.answer.commandermisc.handlers import _seed_missing_tasks
        try:
            _seed_missing_tasks(commander_id, now, newly)
        except Exception:
            pass
        try:
            rows = fetch_commander_tasks(commander_id, sorted(valid_set))
        except Exception:
            rows = []
        accepted = {r.task_id for r in rows}
        claimed = {r.task_id for r in rows if r.submit_time > 0}

    # data3 = the day of the earliest group that is not fully claimed (the
    # page renders that group's tasks); the last group once everything is
    # claimed. Never below day 1.
    day = len(groups)
    for idx, group in enumerate(groups):
        gids = [t for t in group if t in valid_set]
        if gids and not all(t in claimed for t in gids):
            day = idx + 1
            break
    day = max(1, min(day, len(groups)))

    # Persist the day and, on a first-ever accept, the personal start anchor
    # (data2) that the calendar gate counts from.
    try:
        from src.orm.activity_store_state import (
            get_activity_store_data2_sync,
            set_activity_store_day_state_sync,
        )
        anchor = get_activity_store_data2_sync(commander_id, template.id)
        if anchor <= 0:
            # first accept of this run: stamp the anchor (day-1 task accept)
            set_activity_store_day_state_sync(commander_id, template.id, now, day, update_anchor=True)
        else:
            set_activity_store_day_state_sync(commander_id, template.id, anchor, day, update_anchor=False)
    except Exception:
        pass

    # Original reply shape: SC_20003 carries the day's rows (the client's
    # TaskProxy adds them via addActData); SC_11203 is result-only.
    # SC_20003.info is TASK_ADD (same id/progress/accept_time/submit_time
    # fields as TASKINFO, but its own message type). The day's rows are
    # pushed on EVERY cmd=1 while the day is unfinished, not only on the
    # handout: the client's updateActivityTaskStatus loop only stops once
    # the day's VOs exist in TaskProxy, and a VO lost to a manual DB edit /
    # missed push would otherwise leave it re-sending cmd=1 forever
    # (addTask routes duplicates into tmpInfo, so re-sends are harmless).
    response = protobuf.SC_11203(result=0)
    push_ids = list(newly) if newly else list(current_day_ids)
    if current_day_ids and not newly:
        missing = [t for t in current_day_ids if t not in accepted]
        if missing:
            from src.answer.commandermisc.handlers import _seed_missing_tasks
            try:
                _seed_missing_tasks(commander_id, now, missing)
            except Exception:
                pass
            try:
                rows = fetch_commander_tasks(commander_id, sorted(valid_set))
            except Exception:
                rows = []
            push_ids = current_day_ids
    if push_ids:
        by_id = {r.task_id: r for r in rows}
        push = protobuf.SC_20003()
        for tid in push_ids:
            r = by_id.get(tid)
            push.info.append(protobuf.TASK_ADD(
                id=int(tid), progress=int(r.progress or 0) if r else 0,
                accept_time=int(r.accept_time or now) if r else now, submit_time=int(r.submit_time or 0) if r else 0))
        asyncio.create_task(client.send_message(20003, push))

    log_event("Activities", "TaskListSync",
              f"activity={template.id} cmd={cmd} arg1={arg1} groups={len(groups)} "
              f"unlocked={unlocked} new={len(newly)} day={day}",
              LOG_LEVEL_DEBUG)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
