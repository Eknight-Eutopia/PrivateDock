import asyncio
import json
import random
import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.db.store import get_default_store
from src.logger.logger import log_event, LOG_LEVEL_ERROR
from src.orm.item import resolve_virtual_item_drops
from src.config.coin_override import get_coin_range

from .helpers import (
    TECHNOLOGY_OK,
    TECHNOLOGY_INVALID,
    TECHNOLOGY_PERSIST,
    get_or_create_technology_research_state,
    normalize_technology_refresh_flag,
    has_active_technology,
    find_technology_pool,
    find_technology_project,
    build_technology_refresh_pools,
    carry_pool_targets,
    get_technology_template,
    can_consume_technology_cost,
    consume_technology_cost,
    grant_technology_rewards,
    build_drop_info_list,
    is_valid_catchup_target,
    grant_catchup_blueprints,
    save_catchup_counters,
    list_config_entries,
    max_technology_blueprint_version,
    current_technology_day,
)


def _expand_technology_rewards(rewards: list) -> list:
    """Resolve raw template drops into concrete drops.

    Mystery virtual items (e.g. 'Random Blueprint' 52001, 'Random Gear Design'
    52002/52003) expand into their real contents so the client popup and bag show
    the actual item, not the unopenable wrapper. Coin drops (59001 -> gold) get a
    randomized amount from configurations/coin_override.json when set.
    Returns a list of (type, id, number) tuples ready to grant and to send.
    """
    lo, hi = get_coin_range()
    out = []
    for r in rewards:
        rt = r.get("type", r[0] if isinstance(r, (list, tuple)) else 0)
        rid = r.get("id", r[1] if isinstance(r, (list, tuple)) else 0)
        rn = r.get("number", r[2] if isinstance(r, (list, tuple)) else 0)
        for (t, i, c) in resolve_virtual_item_drops(rid, rn, rt):
            if hi > 0 and t == 1 and i == 1:
                c = random.randint(lo, hi)
            out.append((t, i, c))
    return out


def handle_technology_refresh_list(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        cid = client.commander.commander_id
    except (AttributeError, TypeError):
        return 0, 11001, None

    try:
        state = get_or_create_technology_research_state(cid)
    except Exception as e:
        log_event("Technology", "RefreshList", f"failed to get/create state: {e}", LOG_LEVEL_ERROR)
        return 0, 11001, None

    try:
        normalized = normalize_technology_refresh_flag(state)
        if normalized:
            store = get_default_store()
            cid2 = state.get("commander_id", cid)
            if not isinstance(cid2, int):
                cid2 = cid
            pools_raw = json.dumps(state.get("refresh_pools", []))
            queue_raw = json.dumps(state.get("queue", []))
            store.execute(
                "UPDATE technology_research_states SET refresh_flag = $2, refresh_day = $3, refresh_pools = $4::jsonb, queue = $5::jsonb, updated_at = NOW() WHERE commander_id = $1",
                cid2, state["refresh_flag"], state["refresh_day"], pools_raw, queue_raw
            )
    except Exception as e:
        log_event("Technology", "RefreshList", f"failed to persist state: {e}", LOG_LEVEL_ERROR)

    try:
        asyncio.create_task(_send_technology_refresh(client, state))
    except Exception as e:
        log_event("Technology", "RefreshList", f"failed to send refresh: {e}", LOG_LEVEL_ERROR)
    return 0, 63000, None


def _build_catchup_pursuings(state: dict) -> list:
    """TECHPURSUING entries for the SC_63000 catchup block: one per series
    version in technology_catchup_template (official sends every version,
    including untouched/finished ones -- capture 20260905: versions 3, 2, 1
    with 1/300 counters), carrying the shared non-UR counter (`number`) and
    per-UR-ship counters (`dr_numbers`). The counters shape mirrors the
    client's TechnologyCatchup VO (ssrNum shared, urNums per ship)."""
    counters = state.get("catchup_counters", {}) or {}
    ssr_by_version = counters.get("ssr", {}) or {}
    dr_by_version = counters.get("dr", {}) or {}
    versions = []
    try:
        for e in list_config_entries("ShareCfg/technology_catchup_template.json"):
            vid = int(e.get("id", 0) or 0)
            if vid and vid not in versions:
                versions.append(vid)
    except Exception:
        versions = []
    cv = int(state.get("catchup_version", 0) or 0)
    if cv and cv not in versions:
        versions.append(cv)  # crash guard: the selected version must be present
    pursuings = []
    for vid in sorted(versions):
        p = protobuf.TECHPURSUING()
        p.version = vid
        p.number = int(ssr_by_version.get(str(vid), 0) or 0)
        for ship_id, amount in (dr_by_version.get(str(vid), {}) or {}).items():
            try:
                dr = protobuf.DR_NUMBER()
                dr.id = int(ship_id)
                dr.number = int(amount or 0)
            except (TypeError, ValueError):
                continue
            p.dr_numbers.append(dr)
        pursuings.append(p)
    return pursuings


async def _send_technology_refresh(client: Client, state: dict) -> None:
    """Build and send a full SC_63000 (refresh_list + queue + catchup).

    The client only rebuilds its research queue from SC_63000 (it moves techs
    into the queue locally on CS_63013 with each item's own running timer, so a
    queued set shows every item as 'doing' unless the server pushes the
    sequential finish times via this packet).
    """
    response = protobuf.SC_63000()
    response.refresh_list.extend(_build_technology_refresh_list(state))
    response.refresh_flag = state.get("refresh_flag", 0)
    catchup = protobuf.TECHNOLOGYCATCHUP()
    cv = state.get("catchup_version", 0)
    ct = state.get("catchup_target", 0)
    catchup.version = cv
    catchup.target = ct
    # The client's TechnologyProxy:updateTecCatchup iterates `catchup.pursuings`
    # to populate `catchupData`; if it is empty while version/target are non-zero,
    # getCurCatchNum() indexes a nil entry and throws. That throw aborts the
    # on(63000) callback before updateTechnologyQueue runs, leaving `queue` nil,
    # which later crashes the main menu (getPlanningTechnologys -> ipairs(nil)).
    pursuings = _build_catchup_pursuings(state)
    if not pursuings:
        # Config missing entirely -> zero the selection and send one zero entry.
        catchup.version = 0
        catchup.target = 0
        pursuing = protobuf.TECHPURSUING()
        pursuing.version = 1
        pursuing.number = 0
        pursuings = [pursuing]
    catchup.pursuings.extend(pursuings)
    response.catchup.CopyFrom(catchup)
    response.queue.extend(_build_technology_queue_list(state))

    await client.send_message(63000, response)


def handle_start_technology_research(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_63001()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 63002, e

    response = protobuf.SC_63002()
    response.result = TECHNOLOGY_INVALID
    response.time = 0

    tech_id = payload.tech_id
    refresh_id = payload.refresh_id
    if tech_id == 0 or refresh_id == 0:
        asyncio.create_task(client.send_message(63002, response))
        return 0, 63002, None

    state = get_or_create_technology_research_state(client.commander.commander_id)
    normalize_technology_refresh_flag(state)

    pool, ok = find_technology_pool(state, refresh_id)
    if not ok:
        asyncio.create_task(client.send_message(63002, response))
        return 0, 63002, None

    project, ok = find_technology_project(pool, tech_id)
    if not ok:
        asyncio.create_task(client.send_message(63002, response))
        return 0, 63002, None

    now_unix = int(time.time())
    if has_active_technology(state, now_unix):
        asyncio.create_task(client.send_message(63002, response))
        return 0, 63002, None

    template = get_technology_template(tech_id)
    if not can_consume_technology_cost(client.commander, template.get("consume", [])):
        asyncio.create_task(client.send_message(63002, response))
        return 0, 63002, None

    try:
        consume_technology_cost(client.commander.commander_id, template.get("consume", []))
    except Exception as e:
        log_event("Technology", "StartResearch", f"consume failed: {e}", LOG_LEVEL_ERROR)
        response.result = TECHNOLOGY_PERSIST
        asyncio.create_task(client.send_message(63002, response))
        return 0, 63002, None

    queue = state.get("queue", [])
    if queue:
        finish = queue[-1]["finish_time"] + template.get("time", 60)
    else:
        finish = now_unix + template.get("time", 60)
    project["finish_time"] = finish
    store = get_default_store()
    pools_raw = json.dumps(state["refresh_pools"])
    queue_raw = json.dumps(state["queue"])
    store.execute(
        "UPDATE technology_research_states SET refresh_pools = $2::jsonb, queue = $3::jsonb, updated_at = NOW() WHERE commander_id = $1",
        state["commander_id"], pools_raw, queue_raw
    )

    response.result = TECHNOLOGY_OK
    response.time = finish
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 111, 0, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    asyncio.create_task(client.send_message(63002, response))
    return 0, 63002, None


def handle_finish_technology_research(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_63003()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 63004, e

    response = protobuf.SC_63004()
    response.result = TECHNOLOGY_INVALID

    tech_id = payload.tech_id
    refresh_id = payload.refresh_id
    if tech_id == 0 or refresh_id == 0:
        asyncio.create_task(client.send_message(63004, response))
        return 0, 63004, None

    state = get_or_create_technology_research_state(client.commander.commander_id)
    now_unix = int(time.time())
    normalize_technology_refresh_flag(state)

    pool, ok = find_technology_pool(state, refresh_id)
    if not ok:
        asyncio.create_task(client.send_message(63004, response))
        return 0, 63004, None

    project, ok = find_technology_project(pool, tech_id)
    if not ok or project.get("finish_time", 0) == 0 or project["finish_time"] > now_unix:
        asyncio.create_task(client.send_message(63004, response))
        return 0, 63004, None

    template = get_technology_template(tech_id)
    rewards = build_drop_info_list(template.get("drop_client", []))
    resolved = _expand_technology_rewards(rewards)
    try:
        grant_technology_rewards(client.commander.commander_id, resolved)
    except Exception as e:
        log_event("Technology", "FinishResearch", f"grant failed: {e}", LOG_LEVEL_ERROR)
        response.result = TECHNOLOGY_PERSIST
        asyncio.create_task(client.send_message(63004, response))
        return 0, 63004, None

    project["finish_time"] = 0
    seed = now_unix + client.commander.commander_id
    new_pools = build_technology_refresh_pools(seed)
    carry_pool_targets(state, new_pools)
    state["refresh_pools"] = new_pools
    store = get_default_store()
    pools_raw = json.dumps(state["refresh_pools"])
    queue_raw = json.dumps(state["queue"])
    store.execute(
        "UPDATE technology_research_states SET refresh_pools = $2::jsonb, queue = $3::jsonb, updated_at = NOW() WHERE commander_id = $1",
        state["commander_id"], pools_raw, queue_raw
    )

    response.result = TECHNOLOGY_OK
    # Catch-up bonus: 1 blueprint of the selected catch-up ship per completed
    # project, subject to the per-series obtain_max caps.
    try:
        catchup_granted = grant_catchup_blueprints(state, 1)
        if catchup_granted:
            save_catchup_counters(client.commander.commander_id, state["catchup_counters"])
            for d in catchup_granted:
                drop = protobuf.DROPINFO()
                drop.type = d["type"]
                drop.id = d["id"]
                drop.number = d["number"]
                response.catchup_list.append(drop)
    except Exception as e:
        log_event("Technology", "CatchupGrant", f"failed: {e}", LOG_LEVEL_ERROR)
    # Task progress: completing a Technology research project advances every
    # "Complete X Research Projects" / "Conduct research X times" task
    # (sub_type 110).
    try:
        from src.answer.task_handlers import schedule_emit
        schedule_emit(client, 110, 0, 1)
    except Exception:
        pass
    for (t, i, c) in resolved:
        drop = protobuf.DROPINFO()
        drop.type = t
        drop.id = i
        drop.number = c
        response.common_list.append(drop)
    refresh_list = _build_technology_refresh_list(state)
    response.refresh_list.extend(refresh_list)

    asyncio.create_task(client.send_message(63004, response))
    asyncio.create_task(_send_technology_refresh(client, state))
    return 0, 63004, None


def handle_stop_technology_research(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_63005()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 63006, e

    response = protobuf.SC_63006()
    response.result = TECHNOLOGY_INVALID

    tech_id = payload.tech_id
    refresh_id = payload.refresh_id
    if tech_id == 0 or refresh_id == 0:
        asyncio.create_task(client.send_message(63006, response))
        return 0, 63006, None

    state = get_or_create_technology_research_state(client.commander.commander_id)
    now_unix = int(time.time())
    normalize_technology_refresh_flag(state)

    pool, ok = find_technology_pool(state, refresh_id)
    if not ok:
        asyncio.create_task(client.send_message(63006, response))
        return 0, 63006, None

    project, ok = find_technology_project(pool, tech_id)
    if not ok or project.get("finish_time", 0) == 0 or project["finish_time"] <= now_unix:
        asyncio.create_task(client.send_message(63006, response))
        return 0, 63006, None

    project["finish_time"] = 0
    store = get_default_store()
    pools_raw = json.dumps(state["refresh_pools"])
    queue_raw = json.dumps(state["queue"])
    store.execute(
        "UPDATE technology_research_states SET refresh_pools = $2::jsonb, queue = $3::jsonb, updated_at = NOW() WHERE commander_id = $1",
        state["commander_id"], pools_raw, queue_raw
    )

    response.result = TECHNOLOGY_OK
    asyncio.create_task(client.send_message(63006, response))
    return 0, 63006, None


def handle_refresh_technology_projects(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_63007()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 63008, e

    response = protobuf.SC_63008()
    response.result = TECHNOLOGY_INVALID

    if payload.type != 1:
        asyncio.create_task(client.send_message(63008, response))
        return 0, 63008, None

    state = get_or_create_technology_research_state(client.commander.commander_id)
    now_unix = int(time.time())
    normalize_technology_refresh_flag(state)

    if state.get("refresh_flag") != 0:
        asyncio.create_task(client.send_message(63008, response))
        return 0, 63008, None

    if has_active_technology(state, now_unix):
        asyncio.create_task(client.send_message(63008, response))
        return 0, 63008, None

    seed = now_unix + client.commander.commander_id
    pools = build_technology_refresh_pools(seed)
    carry_pool_targets(state, pools)
    state["refresh_pools"] = pools
    state["refresh_flag"] = 1
    state["refresh_day"] = current_technology_day()

    store = get_default_store()
    pools_raw = json.dumps(state["refresh_pools"])
    queue_raw = json.dumps(state["queue"])
    store.execute(
        "UPDATE technology_research_states SET refresh_flag = $2, refresh_day = $3, refresh_pools = $4::jsonb, queue = $5::jsonb, updated_at = NOW() WHERE commander_id = $1",
        state["commander_id"], state["refresh_flag"], state["refresh_day"], pools_raw, queue_raw
    )

    response.result = TECHNOLOGY_OK
    refresh_list = _build_technology_refresh_list(state)
    response.refresh_list.extend(refresh_list)

    asyncio.create_task(client.send_message(63008, response))
    return 0, 63008, None


def handle_change_refresh_technology_tendency(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_63009()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 63010, e

    response = protobuf.SC_63010()
    response.result = TECHNOLOGY_INVALID

    refresh_id = payload.id
    target = payload.target
    if refresh_id == 0:
        asyncio.create_task(client.send_message(63010, response))
        return 0, 63010, None

    max_target = max_technology_blueprint_version()
    if target > max_target:
        asyncio.create_task(client.send_message(63010, response))
        return 0, 63010, None

    state = get_or_create_technology_research_state(client.commander.commander_id)
    normalize_technology_refresh_flag(state)

    pool, ok = find_technology_pool(state, refresh_id)
    if not ok:
        asyncio.create_task(client.send_message(63010, response))
        return 0, 63010, None

    pool["target"] = target
    store = get_default_store()
    pools_raw = json.dumps(state["refresh_pools"])
    store.execute(
        "UPDATE technology_research_states SET refresh_pools = $2::jsonb, updated_at = NOW() WHERE commander_id = $1",
        state["commander_id"], pools_raw
    )

    response.result = TECHNOLOGY_OK
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 112, 0, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    asyncio.create_task(client.send_message(63010, response))
    return 0, 63010, None


def handle_select_technology_catchup_target(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_63011()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 63012, e

    response = protobuf.SC_63012()
    response.result = TECHNOLOGY_INVALID

    version = payload.version
    target = payload.target
    if version == 0 or target == 0:
        asyncio.create_task(client.send_message(63012, response))
        return 0, 63012, None

    ok = is_valid_catchup_target(version, target)
    if not ok:
        asyncio.create_task(client.send_message(63012, response))
        return 0, 63012, None

    state = get_or_create_technology_research_state(client.commander.commander_id)
    normalize_technology_refresh_flag(state)

    # Re-selection is allowed at any time (wiki: "you can choose which ship
    # will get bonus blueprints, and this can be changed at any time"); only
    # the already-granted counters stay as they are.
    state["catchup_version"] = version
    state["catchup_target"] = target

    store = get_default_store()
    pools_raw = json.dumps(state["refresh_pools"])
    queue_raw = json.dumps(state["queue"])
    counters_raw = json.dumps(state.get("catchup_counters", {}) or {})
    store.execute(
        "UPDATE technology_research_states SET catchup_version = $2, catchup_target = $3, refresh_pools = $4::jsonb, queue = $5::jsonb, catchup_counters = $6::jsonb, updated_at = NOW() WHERE commander_id = $1",
        state["commander_id"], version, target, pools_raw, queue_raw, counters_raw
    )

    response.result = TECHNOLOGY_OK
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 112, 0, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    asyncio.create_task(client.send_message(63012, response))
    return 0, 63012, None


def handle_join_technology_queue(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_63013()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 63014, e

    response = protobuf.SC_63014()
    response.result = TECHNOLOGY_INVALID

    tech_id = payload.tech_id
    refresh_id = payload.refresh_id
    if tech_id == 0 or refresh_id == 0:
        asyncio.create_task(client.send_message(63014, response))
        return 0, 63014, None

    state = get_or_create_technology_research_state(client.commander.commander_id)
    now_unix = int(time.time())
    normalize_technology_refresh_flag(state)

    if len(state.get("queue", [])) >= 5:
        asyncio.create_task(client.send_message(63014, response))
        return 0, 63014, None

    pool, ok = find_technology_pool(state, refresh_id)
    if not ok:
        asyncio.create_task(client.send_message(63014, response))
        return 0, 63014, None

    project, ok = find_technology_project(pool, tech_id)
    if not ok or project.get("finish_time", 0) == 0 or project["finish_time"] <= now_unix:
        asyncio.create_task(client.send_message(63014, response))
        return 0, 63014, None

    queue = state.setdefault("queue", [])
    template = get_technology_template(tech_id)
    ttime = template.get("time", 60)
    if queue:
        new_finish = queue[-1]["finish_time"] + ttime
    else:
        new_finish = project["finish_time"]
    queue.append({
        "tech_id": tech_id,
        "refresh_id": refresh_id,
        "finish_time": new_finish,
    })
    queue.sort(key=lambda x: x["finish_time"])
    project["finish_time"] = 0

    seed = now_unix + client.commander.commander_id
    new_pools = build_technology_refresh_pools(seed)
    carry_pool_targets(state, new_pools)
    state["refresh_pools"] = new_pools

    store = get_default_store()
    pools_raw = json.dumps(state["refresh_pools"])
    queue_raw = json.dumps(state["queue"])
    store.execute(
        "UPDATE technology_research_states SET refresh_pools = $2::jsonb, queue = $3::jsonb, updated_at = NOW() WHERE commander_id = $1",
        state["commander_id"], pools_raw, queue_raw
    )

    response.result = TECHNOLOGY_OK
    refresh_list = _build_technology_refresh_list(state)
    response.refresh_list.extend(refresh_list)

    asyncio.create_task(client.send_message(63014, response))
    asyncio.create_task(_send_technology_refresh(client, state))
    return 0, 63014, None


def handle_finish_queue_technology(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_63015()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 63016, e

    response = protobuf.SC_63016()
    response.result = TECHNOLOGY_INVALID

    if payload.id != 0:
        asyncio.create_task(client.send_message(63016, response))
        return 0, 63016, None

    state = get_or_create_technology_research_state(client.commander.commander_id)
    now_unix = int(time.time())
    normalize_technology_refresh_flag(state)

    queue = state.get("queue", [])
    if not queue:
        asyncio.create_task(client.send_message(63016, response))
        return 0, 63016, None

    claimed = []
    remaining = []
    for entry in queue:
        if entry["finish_time"] <= now_unix:
            claimed.append(entry)
        else:
            remaining.append(entry)

    if not claimed:
        asyncio.create_task(client.send_message(63016, response))
        return 0, 63016, None

    drops = []
    catchup_total = 0
    for entry in claimed:
        template = get_technology_template(entry["tech_id"])
        rewards = build_drop_info_list(template.get("drop_client", []))
        resolved = _expand_technology_rewards(rewards)
        grant_technology_rewards(client.commander.commander_id, resolved)
        tech_drop = protobuf.TECHNOLOGYDROP()
        for (t, i, c) in resolved:
            drop = protobuf.DROPINFO()
            drop.type = t
            drop.id = i
            drop.number = c
            tech_drop.common_list.append(drop)
        # Catch-up bonus per queued project (official SC_63016 drops each carry
        # catchup_list with the selected target's blueprint x1).
        try:
            catchup_granted = grant_catchup_blueprints(state, 1)
            if catchup_granted:
                catchup_total += len(catchup_granted)
                for d in catchup_granted:
                    drop = protobuf.DROPINFO()
                    drop.type = d["type"]
                    drop.id = d["id"]
                    drop.number = d["number"]
                    tech_drop.catchup_list.append(drop)
        except Exception as e:
            log_event("Technology", "CatchupGrant", f"queue failed: {e}", LOG_LEVEL_ERROR)
        drops.append(tech_drop)

    if catchup_total:
        # Persist only when something was granted (a capped target yields no
        # drops and leaves the counters untouched).
        save_catchup_counters(client.commander.commander_id, state["catchup_counters"])

    state["queue"] = remaining
    store = get_default_store()
    pools_raw = json.dumps(state["refresh_pools"])
    queue_raw = json.dumps(state["queue"])
    store.execute(
        "UPDATE technology_research_states SET refresh_pools = $2::jsonb, queue = $3::jsonb, updated_at = NOW() WHERE commander_id = $1",
        state["commander_id"], pools_raw, queue_raw
    )

    response.result = TECHNOLOGY_OK
    response.drops.extend(drops)

    # Task progress: claiming finished research-queue projects advances every
    # "Complete X Research Projects" task (sub_type 110, e.g. daily 7209),
    # mirroring handle_finish_technology_research (CS_63004).
    try:
        from src.answer.task_handlers import schedule_emit
        schedule_emit(client, 110, 0, len(claimed))
    except Exception:
        pass

    asyncio.create_task(client.send_message(63016, response))
    return 0, 63016, None


def _build_technology_refresh_list(state: dict) -> list:
    result = []
    for pool in state.get("refresh_pools", []):
        entry = protobuf.TECHNOLOGYREFRESH()
        entry.id = pool["id"]
        entry.target = pool.get("target", 0)
        for project in pool.get("technologies", []):
            info = protobuf.TECHNOLOGYINFO()
            info.id = project["tech_id"]
            info.time = project.get("finish_time", 0)
            entry.technologys.append(info)
        result.append(entry)
    return result


def _build_technology_queue_list(state: dict) -> list:
    result = []
    for entry in state.get("queue", []):
        info = protobuf.TECHNOLOGYINFO()
        info.id = entry["tech_id"]
        info.time = entry["finish_time"]
        result.append(info)
    return result
