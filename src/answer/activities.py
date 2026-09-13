from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.logger.logger import log_event, LOG_LEVEL_DEBUG, LOG_LEVEL_WARN, LOG_LEVEL_ERROR
from src.protobuf import protobuf


from src.answer.educate.helpers import append_unique_uint32 as _append_unique_uint32


def _filter_permanent_activity_ids(ids: list, allowed: set) -> list:
    return [aid for aid in ids if aid in allowed]


def _to_uint32_list(values: list) -> list:
    return [int(v) for v in values]


def _parse_day_list_json(raw) -> list:
    import json
    if not raw:
        return []
    if isinstance(raw, list):
        return [int(v) for v in raw]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [int(v) for v in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _load_permanent_activity_id_set() -> set:
    from src.orm.config_entry import list_config_entries
    entries = list_config_entries("ShareCfg/activity_task_permanent.json")
    ids = set()
    for entry in entries:
        data = entry.data if hasattr(entry, "data") else entry
        if isinstance(data, dict):
            aid = data.get("id", 0)
            if aid:
                ids.add(int(aid))
        elif isinstance(data, (int, float)):
            ids.add(int(data))
    return ids


def _activity_stop_time(raw) -> int:
    from src.answer.activity_builders import activity_stop_time
    return activity_stop_time(raw)


def _info_to_proto(info: dict) -> protobuf.ACTIVITYINFO:
    msg = protobuf.ACTIVITYINFO()
    msg.id = info.get("id", 0)
    msg.stop_time = info.get("stop_time", 0)
    msg.data1 = info.get("data1", 0)
    msg.data2 = info.get("data2", 0)
    msg.data3 = info.get("data3", 0)
    msg.data4 = info.get("data4", 0)
    msg.data1_list.extend(info.get("data1_list", []))
    msg.data2_list.extend(info.get("data2_list", []))
    msg.data3_list.extend(info.get("data3_list", []))
    msg.data4_list.extend(info.get("data4_list", []))
    msg.str_data1 = info.get("str_data1", "")
    for item in info.get("date1_key_value_list", []):
        kv_list = protobuf.KEYVALUELIST_P11()
        kv_list.key = item.get("key", 0)
        for v in item.get("value_list", []):
            kv = protobuf.KEYVALUE_P11()
            if isinstance(v, dict):
                kv.key = v.get("key", 0)
                kv.value = v.get("value", 0)
            else:
                kv.value = int(v)
            kv_list.value_list.append(kv)
        kv_list.value = item.get("value", 0)
        msg.date1_key_value_list.append(kv_list)
    for item in info.get("group_list", []):
        group = protobuf.GROUPINFO_P11()
        if isinstance(item, dict):
            group.id = item.get("id", 0)
            group.ship_list.extend(item.get("ship_list", []) if isinstance(item.get("ship_list"), list) else [item.get("ship_list", 0)])
            commanders = item.get("commanders", [])
            if isinstance(commanders, list):
                for c in commanders:
                    ci = protobuf.COMMANDERSINFO()
                    if isinstance(c, dict):
                        ci.pos = c.get("pos", 0)
                        ci.id = c.get("id", 0)
                    group.commanders.append(ci)
        msg.group_list.append(group)
    for item in info.get("collection_list", []):
        c = protobuf.COLLECTIONINFO()
        if isinstance(item, dict):
            c.id = item.get("id", 0)
            c.finish_time = item.get("finish_time", 0)
            c.over_time = item.get("over_time", 0)
            c.ship_id_list.extend(item.get("ship_id_list", []) if isinstance(item.get("ship_id_list"), list) else [item.get("ship_id_list", 0)])
        msg.collection_list.append(c)
    for item in info.get("task_list", []):
        t = protobuf.TASKINFO()
        if isinstance(item, dict):
            t.id = item.get("id", 0)
            t.progress = item.get("progress", 0)
            t.accept_time = item.get("accept_time", 0)
            t.submit_time = item.get("submit_time", 0)
        msg.task_list.append(t)
    for item in info.get("buff_list", []):
        b = protobuf.BENEFITBUFF()
        if isinstance(item, dict):
            b.id = item.get("id", 0)
            b.timestamp = item.get("timestamp", 0)
        msg.buff_list.append(b)
    return msg


def _fallback_rows() -> list[dict]:
    from src.orm.activity_server import FALLBACK_ACTIVITY_IDS
    return [
        {
            "activity_id": int(aid), "enabled": True, "is_permanent": True,
            "start_time": 0, "end_time": 0, "sort_order": 0, "note": "",
        }
        for aid in FALLBACK_ACTIVITY_IDS
    ]
def handle_activities(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    import time as _time
    _now = int(_time.time())

    # Candidate set comes from the server_activities registry (operational
    # data). If the table is missing (migration not applied) or empty (import
    # not run on a fresh DB), degrade to the historical built-in list so login
    # still serves the baseline activities.
    from src.orm.activity_server import get_server_activities_sync
    try:
        rows = get_server_activities_sync(enabled_only=True)
    except Exception as e:
        log_event("Activities", "Handle",
                  f"failed to load server_activities; using built-in fallback: {e}",
                  LOG_LEVEL_ERROR)
        rows = None
    if not rows:
        rows = _fallback_rows()

    try:
        from src.orm.activity_permanent_state import get_or_create_activity_permanent_state
        state_orm = get_or_create_activity_permanent_state(client.commander.commander_id)
        state = {c.name: getattr(state_orm, c.name) for c in state_orm.__table__.columns}
    except Exception as e:
        log_event("Activities", "Handle",f"failed to get_or_create_activity: {e}", LOG_LEVEL_ERROR)
        return 0, 11200, e

    try:
        permanent_ids = _load_permanent_activity_id_set()
    except Exception as e:
        log_event("Activities", "Handle",f"failed to _load_permanent_activity_id_set: {e}", LOG_LEVEL_ERROR)
        return 0, 11200, e

    finished = _filter_permanent_activity_ids(
        _to_uint32_list(state.get("finished_activity_ids", [])),
        permanent_ids,
    )
    finished_set = set(finished)

    candidates = []
    for row in rows:
        aid = int(row["activity_id"])
        if aid in finished_set:
            continue
        candidates.append((aid, row))

    current_id = int(state.get("current_activity_id", 0) or 0)
    if current_id and current_id in permanent_ids and current_id not in finished_set:
        if current_id not in {aid for aid, _ in candidates}:
            candidates.append((
                current_id,
                {"activity_id": current_id, "enabled": True, "is_permanent": True,
                 "start_time": 0, "end_time": 0, "sort_order": 0, "note": ""},
            ))

    response = protobuf.SC_11200()

    if not candidates:
        data = response.SerializeToString()
        header = generate_packet_header(11200, data, client.packet_index)
        client.write_to_buffer(header + data)
        return 0, 11001, None

    from src.answer.activity_templates import load_activity_template
    from src.answer.activity_builders import build_activity_info
    from src.answer.activity_constants import ACTIVITY_TYPES_THAT_CREATE_BUILD_POOLS

    _t0 = _time.monotonic()
    _activity_ms: list[tuple[float, int]] = []

    for activity_id, row in candidates:
        _a0 = _time.monotonic()
        template = load_activity_template(activity_id)
        if template is None:
            log_event("Activities", "Handle",
                      f"activity {activity_id} has no template; skipping",
                      LOG_LEVEL_WARN)
            continue
        # Build-pool activities (Wishing Well / new-server build) have no
        # server-side event-build logic; serving them breaks the client's
        # Build menu, so never expose them even if enabled in the registry.
        if template.type in ACTIVITY_TYPES_THAT_CREATE_BUILD_POOLS:
            log_event("Activities", "Handle",
                      f"activity {activity_id} is a build-pool type; skipping",
                      LOG_LEVEL_WARN)
            continue

        is_permanent = bool(row.get("is_permanent", False))
        start_t = int(row.get("start_time", 0) or 0)
        end_t = int(row.get("end_time", 0) or 0)

        # Military Exercise (type 7, id 7) ships with a historical fixed
        # timer in activity_template that is long expired. The client gates
        # the Exercise menu on the activity's stop_time (showing
        # "This event has not yet started or has already ended" when it is
        # in the past), so force an active window aligned with the real
        # exercise season: 2-week blocks starting Monday 00:00 region time
        # (see exercise.helpers.season_bounds - the season state rotation
        # uses the same boundary).
        if template.type == 7 or template.id == 7:
            try:
                from src.answer.exercise.helpers import season_bounds as _season_bounds
                _, _s_start, stop_time = _season_bounds()
            except Exception:
                stop_time = 0
            if stop_time <= _now:
                stop_time = _now + 14 * 24 * 3600
        else:
            stop_time = _activity_stop_time(template.time)
            if is_permanent:
                stop_time = 0
            else:
                # Temporaries: only serve while their window is live; an
                # ended / not-yet-started event is skipped entirely.
                if end_t > 0 and _now > end_t:
                    log_event("Activities", "Handle",
                              f"activity {activity_id} ended; skipping", LOG_LEVEL_WARN)
                    _activity_ms.append((_time.monotonic() - _a0, activity_id))
                    continue
                if start_t > 0 and _now < start_t:
                    log_event("Activities", "Handle",
                              f"activity {activity_id} not started; skipping", LOG_LEVEL_WARN)
                    _activity_ms.append((_time.monotonic() - _a0, activity_id))
                    continue
                if not stop_time and end_t:
                    stop_time = end_t

        info = build_activity_info(template, stop_time)
        if info is None:
            _activity_ms.append((_time.monotonic() - _a0, activity_id))
            continue

        from src.orm.activity_fleet import load_activity_fleet_groups_sync
        try:
            groups, found = load_activity_fleet_groups_sync(client.commander.commander_id, template.id)
        except Exception:
            groups, found = None, False
        if found and groups:
            info["group_list"] = groups

        from src.orm.activity_store import get_activity_store_state_sync
        try:
            store_state = get_activity_store_state_sync(client.commander.commander_id, template.id)
            if store_state is not None:
                info["data1"] = store_state.data1
                info["data2"] = store_state.data2
                info["data3"] = store_state.data3
                info["str_data1"] = store_state.str_data1
                if template.type == 4:
                    from src.answer.activity_builders import build_level_award_data1_list
                    info["data1_list"] = build_level_award_data1_list(template.config_id, store_state.data1 or 0)
                elif template.type == 1:
                    # BUILDSHIP_1 / Wishing Well (PrayPool): data1 = selected pool,
                    # data1_list = selected focus ship template ids. The client
                    # restores the selection from SC_11200 on login.
                    info["data1_list"] = _parse_day_list_json(store_state.data1_list)
                elif template.type == 6:
                    from src.answer.activity_sign import current_month_id, _now_unix
                    year, month = current_month_id(_now_unix())
                    info["data1"] = year
                    info["data2"] = month
                    info["data3"] = store_state.data3
                    if (store_state.data1 or 0) == year and (store_state.data2 or 0) == month:
                        info["data1_list"] = _parse_day_list_json(store_state.data1_list)
                    else:
                        info["data1_list"] = []
                elif template.type == 59:
                    # StoryAwardPage ("Stage Reward"): data1_list = ids of the
                    # stages whose clear reward is already claimed (CS_11202
                    # cmd=1 arg1=stage_id; the client appends arg1 on result=0).
                    info["data1_list"] = _parse_day_list_json(store_state.data1_list)
                elif template.type == 17:
                    # Akashi's Commission (activity 21): data1_list = hidden
                    # touch flags already fired (CS_11202 cmd=2 arg1=flag_id);
                    # the client skips flags present here, so without the
                    # stamp they would re-fire after re-login.
                    info["data1_list"] = _parse_day_list_json(store_state.data1_list)
            elif template.type == 6:
                from src.answer.activity_sign import current_month_id, _now_unix
                year, month = current_month_id(_now_unix())
                info["data1"] = year
                info["data2"] = month
                info["data3"] = 0
                info["data1_list"] = []
        except Exception:
            pass

        if template.type == 71:
            # Fresh Tech Catchup (Training Camp / Dev Missions). The client derives
            # phase tabs + finished phases from THIS activity's state:
            #   data1     = current phase id (official fresh default: 1)
            #   data2     = 1 once the first phase has been started (CS_11202 cmd=3)
            #   data1_list= ids of COMPLETED phases (CS_11202 cmd=1 advances)
            # A phase id present in data1_list renders its cumulative task as
            # Completed, so this MUST reflect genuine progression - never fabricate
            # finished phases. State persists in activity_store_states via the
            # CS_11202 handler (_handle_tec_catchup).
            try:
                st = get_activity_store_state_sync(client.commander.commander_id, template.id)
                d1 = int(getattr(st, "data1", 0) or 0) if st is not None else 0
                d2 = int(getattr(st, "data2", 0) or 0) if st is not None else 0
                d1l = _parse_day_list_json(st.data1_list) if st is not None else []
                info["data1"] = d1 or 1
                info["data2"] = 1 if d2 else 0
                info["data3"] = 0
                info["data1_list"] = [int(x) for x in (d1l or [])]
            except Exception:
                pass

        response.activity_list.append(_info_to_proto(info))
        _activity_ms.append((_time.monotonic() - _a0, activity_id))

    _total_ms = (sum(ms for ms, _ in _activity_ms)) * 1000.0
    if _total_ms >= 300:
        _slowest = sorted(_activity_ms, reverse=True)[:5]
        log_event("Activities", "SC_11200",
                  f"built {len(_activity_ms)} activities in {_total_ms:.0f}ms SLOW; slowest: "
                  + ", ".join(f"id={aid} {ms * 1000.0:.0f}ms" for ms, aid in _slowest),
                  LOG_LEVEL_WARN)
    else:
        log_event("Activities", "SC_11200",
                  f"built {len(_activity_ms)} activities in {_total_ms:.1f}ms",
                  LOG_LEVEL_DEBUG)

    data = response.SerializeToString()
    header = generate_packet_header(11200, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 11001, None