import time
from typing import Optional

from src.logger.logger import log_event, LOG_LEVEL_DEBUG, LOG_LEVEL_ERROR, LOG_LEVEL_WARN
from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.misc.safe_ts import safe_ts
from src.protobuf import protobuf
from src.orm.owned_ship import list_dock_ships
from src.orm.commander_task import (
    create_or_accept_task,
    fetch_existing_task_ids,
    fetch_submitted_task_ids,
    fetch_commander_task_progress_map,
    seed_commander_tasks,
)
from src.answer.profile.helpers import list_config_entries

from .helpers import (
    list_config_entries,
    list_global_skin_restrictions,
    list_global_skin_restriction_windows,
)


def handle_commander_owned_skins(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_12201()
    owned_skins = getattr(client.commander, "owned_skins_map", None)
    if owned_skins is not None:
        for skin_id, skin in owned_skins.items():
            expiry = 0
            if hasattr(skin, "expires_at") and skin.expires_at is not None:
                if hasattr(skin.expires_at, "timestamp"):
                    expiry = safe_ts(skin.expires_at)
                else:
                    expiry = int(skin.expires_at)
            info = protobuf.IDTIMEINFO()
            info.id = skin_id
            info.time = expiry
            response.skin_list.append(info)

    try:
        restrictions = list_global_skin_restrictions()
        for r in restrictions:
            response.forbidden_skin_list.append(r["skin_id"])
            response.forbidden_skin_type.append(r["type"])
    except Exception as e:
        return 0, 12201, e

    try:
        windows = list_global_skin_restriction_windows()
        for w in windows:
            fb = protobuf.SKIN_FORBIDDEN()
            fb.id = w["skin_id"]
            fb.type = w["type"]
            fb.start_time = w["start_time"]
            fb.stop_time = w["stop_time"]
            response.forbidden_list.append(fb)
    except Exception as e:
        return 0, 12201, e

    data = response.SerializeToString()
    header = generate_packet_header(12201, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 12201, None


_MANUAL_CACHE = None


def _manual_config():
    """Cache the tutorial_handbook_task config as the authoritative source for
    manual page structure (sub-tasks, milestones, award thresholds)."""
    global _MANUAL_CACHE
    if _MANUAL_CACHE is not None:
        return _MANUAL_CACHE
    pages = list_config_entries("ShareCfg/tutorial_handbook_task.json")
    subtasks = set()
    milestones = set()
    page_subtasks = {}
    page_tasklist = {}
    page_targets = {}
    page_unlock = {}
    page_ids = []
    for p in pages:
        pid = p["id"]
        page_ids.append(pid)
        tl = p.get("task_list", [])
        page_tasklist[pid] = tl
        subs = []
        for group in tl:
            subs.extend(group[0])
        page_subtasks[pid] = subs
        subtasks.update(subs)
        unlock_ids = list(p.get("unlock", []) or [])
        milestones.update(unlock_ids)
        page_unlock[pid] = unlock_ids
        page_targets[pid] = {
            "target": p.get("target", []),
            "drop_client": p.get("drop_client", []),
        }
    _MANUAL_CACHE = {
        "pages": page_ids,
        "subtasks": subtasks,
        "milestones": milestones,
        "page_subtasks": page_subtasks,
        "page_tasklist": page_tasklist,
        "page_targets": page_targets,
        "page_unlock": page_unlock,
    }
    return _MANUAL_CACHE


def _page_is_locked(cfg: dict, finished: set, pid) -> bool:
    """A manual page is locked while any of its `unlock` milestone tasks is not
    yet submitted. Pages with an empty unlock array (the first Rookie/Guide
    pages) are always open.

    The client (commandermanualproxy.lua) builds every page PRESENT in SC_22300
    with isUnlock=true and its ChangeUnlock() can only ever set true - so the
    server must omit locked pages entirely or the client shows them all open."""
    for uid in cfg["page_unlock"].get(pid, []) or []:
        if uid not in finished:
            return True
    return False


def _locked_manual_subtask_ids(client, _store, commander_id) -> set:
    """Manual sub-tasks of pages whose unlock milestone is not finished yet.

    Progress for these is tracked in the DB but must NOT be exposed through the
    task sync (SC_20001) or progress pushes (SC_20002): the client badges any
    page tab whose tasks have claimable VOs (CommanderManualPage.ShouldShowTip
    reads TaskProxy directly, even for locked pages) while a locked tab cannot
    be opened to claim, so a visible completed task there is unclaimable.
    When the page unlocks, the client requests its tasks via CS_22302 and the
    stored progress goes out with the TASK_ADD pushes.

    Cached per connection; _recompute_milestones invalidates the cache whenever
    it submits a milestone (the only thing that changes lock state)."""
    if client is not None:
        cached = getattr(client, "_locked_manual_ids", None)
        if cached is not None:
            return cached
    cfg = _manual_config()
    locked: set = set()
    try:
        finished = fetch_submitted_task_ids(commander_id, sorted(cfg["milestones"]))
        for pid, subs in cfg["page_subtasks"].items():
            if _page_is_locked(cfg, finished, pid):
                locked.update(subs)
    except Exception:
        # On failure expose everything rather than hiding everything: a stale
        # badge on a locked tab is cosmetic, a missing task sync is not.
        locked = set()
    if client is not None:
        try:
            client._locked_manual_ids = locked
        except Exception:
            pass
    return locked


def _ensure_manual_award_table():
    # Table lives in sql/0054_commander_manual_awards.sql since 2026-09-02;
    # kept as a no-op so existing call sites do not need changing.
    return None


def _accept_manual_task(client, store, commander_id, tid, now, submit, push_add=True):
    """Accept (and optionally auto-complete) a Commander Manual task.

    The manual sub-tasks are real task_data_template entries (type 17) and progress
    exactly like normal missions through the emit_task_progress pipeline — they are
    matched by (sub_type, target_id) with no type filter, so any in-game action that
    advances a mission of the same kind also advances the matching handbook task.

    submit=True  -> mark complete now (progress=target, submit_time=now) and grant
                    the per-task award. Used ONLY for milestone/page-unlock gates
                    (_recompute_milestones) once their sub-tasks are satisfied.
    submit=False -> accept as an in-progress task (progress=0) and let gameplay
                    (emit_task_progress) fill it. Real partial progress is preserved
                    and already-claimed rows are left alone. Never force-"Completed".
    """
    from src.answer.task_handlers import _load_task_template, _build_task_drops, _apply_drops

    template = _load_task_template(tid)
    if template is None:
        return
    target_num = int(template.get("target_num", 0) or 0) or 1

    row = store.fetchrow(
        "SELECT progress, submit_time FROM commander_tasks WHERE commander_id=$1 AND task_id=$2",
        commander_id, tid,
    )

    if submit:
        if row is not None and row[1] != 0:
            return
        try:
            drops = _build_task_drops(template)
        except Exception as e:
            drops = {}
            log_event("Handbook", "SC_20008", f"task {tid}: drop build failed: {e}", LOG_LEVEL_ERROR)
        store.execute(
            "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
            "VALUES ($1,$2,$3,$4,$5) "
            "ON CONFLICT (commander_id, task_id) DO UPDATE SET progress=$3, submit_time=$5 "
            "WHERE commander_tasks.submit_time=0",
            commander_id, tid, target_num, now, now,
        )
        try:
            if drops:
                _apply_drops(client, drops)
        except Exception as e:
            log_event("Handbook", "SC_20008",
                      f"task {tid}: marked claimed but drop apply failed: {e}", LOG_LEVEL_ERROR)
        if push_add:
            _push_task_add(client, tid, target_num, now, submit_time=now)
        return

    # submit=False: accept as an in-progress task and let gameplay (emit_task_progress)
    # fill it. Never force-"completed". Preserve real partial progress and leave
    # already-claimed rows alone.
    if row is not None:
        if row[1] != 0:
            return
        if push_add:
            _push_task_add(client, tid, row[0] or 0, now)
        return
    create_or_accept_task(commander_id, tid, now)
    if push_add:
        _push_task_add(client, tid, 0, now)


def _seed_missing_tasks( commander_id: int, now: int, ids: list) -> int:
    """Insert progress=0 rows for task ids that have no row yet. ONE select +
    ONE bulk insert instead of a fetchrow per task (login was doing ~320
    sequential round-trips).     Existing rows - partial or claimed - are left
    untouched, matching _accept_manual_task(submit=False) semantics."""
    from src.answer.task_handlers import _load_task_template

    if not ids:
        return 0
    valid = []
    for tid in ids:
        if _load_task_template(tid) is not None:
            valid.append(tid)
    if not valid:
        return 0
    existing = fetch_existing_task_ids(commander_id, valid)
    missing = [t for t in valid if t not in existing]
    if not missing:
        return 0
    seed_commander_tasks(commander_id, missing, now)
    return len(missing)


def _ensure_manual_tasks(client, store, commander_id, now, push_add=False):
    """On login, make sure every Commander Manual sub-task is present and rendered
    correctly, and that milestone gates exist.

    - Tasks not yet in the DB are created IN-PROGRESS (progress=0, submit_time=0).
      They advance through normal gameplay via the emit_task_progress pipeline, so
      the client shows genuine progress bars instead of a false "completed".
    - Tasks already submitted (submit_time != 0, e.g. claimed on the official
      account) are left as-is so the client shows the correct "claimed" state.
      We deliberately do NOT re-open them, otherwise the client auto-claims them
      again on every login and the reward would be granted repeatedly.
    - Milestones complete only when enough of their target page's sub-tasks have
      genuinely reached target progress, so pages unlock as the player progresses.
      The per-task award is granted when the player claims via CS_20005.

    Runs at most once per client connection (both login-chain callers - player
    info SC_22300 build and missions SC_20001 sync - used to execute this whole
    seed twice). Interactive callers (CS_22302, push_add=True) bypass the guard."""
    if not push_add and client is not None and getattr(client, "_manual_ensured", False):
        return
    cfg = _manual_config()
    _t0 = time.monotonic()
    if push_add:
        locked = _locked_manual_subtask_ids(client, store, commander_id)
        for tid in sorted(cfg["subtasks"]):
            if tid in locked:
                # Locked-page tasks stay invisible until the page unlocks
                # (CS_22302 + TASK_ADD carries the stored progress then).
                continue
            _accept_manual_task(client, store, commander_id, tid, now,
                                submit=False, push_add=True)
    else:
        # Only seed sub-tasks of UNLOCKED pages. Locked pages must have no task
        # VOs: the client computes GIVE_ITEM progress from the bag, so a synced
        # locked-page task can read as "finished" and badge the locked tab.
        # Locked pages get their tasks via CS_22302 when they unlock.
        finished_milestones = fetch_submitted_task_ids(commander_id, sorted(cfg["milestones"]))
        allowed: set = set()
        for pid, subs in cfg["page_subtasks"].items():
            if not _page_is_locked(cfg, finished_milestones, pid):
                allowed.update(subs)
        _seed_missing_tasks(commander_id, now, sorted(allowed))
    _t1 = time.monotonic()
    _recompute_milestones(client, store, commander_id, now, push_add=push_add)
    _t2 = time.monotonic()
    _seed_ms = (_t1 - _t0) * 1000.0
    _mile_ms = (_t2 - _t1) * 1000.0
    _msg = (f"cmd={commander_id} subtasks={len(cfg['subtasks'])} seed={_seed_ms:.0f}ms "
            f"milestones={_mile_ms:.0f}ms")
    if _seed_ms + _mile_ms >= 200:
        log_event("Handbook", "EnsureTasks", _msg + " SLOW", LOG_LEVEL_WARN)
    else:
        log_event("Handbook", "EnsureTasks", _msg, LOG_LEVEL_DEBUG)
    if client is not None:
        try:
            client._manual_ensured = True
        except Exception:
            pass


_TECH_CACHE = None


def _tech_task_ids():
    """All Fresh Tech Catchup (activity type 71, template 30445) task ids across
    its 7 phases: each phase is [task_id_list, finish_task_id]. Lua reads these
    from config_data[3] (1-indexed -> Python config_data[2])."""
    global _TECH_CACHE
    if _TECH_CACHE is not None:
        return _TECH_CACHE
    ids = []
    try:
        entries = list_config_entries("ShareCfg/activity_template.json")
        for e in entries:
            d = e if isinstance(e, dict) else None
            if not d or d.get("id") != 30445:
                continue
            cd = d.get("config_data")
            if isinstance(cd, list) and len(cd) > 2:
                for phase in cd[2]:
                    if isinstance(phase, list) and phase:
                        ids.extend(phase[0])
                        if len(phase) > 1:
                            ids.append(phase[1])
            break
    except Exception:
        # Transient failure (DB hiccup, cold start ordering): retry on the next
        # call instead of caching an empty task list for the process lifetime.
        return []
    parsed = sorted(set(ids))
    if parsed:
        _TECH_CACHE = parsed
    return parsed


def _ensure_tech_tasks(client, store, commander_id, now, push_add=False):
    """Seed the Training Camp (Fresh Tech Catchup) tasks as in-progress. The tech
    tab reads each task via TaskProxy:getTaskVO(id); by accepting them into
    commander_tasks (progress=0, submit_time=0) they enter the 20001 task sync and
    advance through normal gameplay (emit_task_progress), so the client shows
    genuine progress instead of a false "completed". Idempotent: an unsubmitted row
    is preserved/created as in-progress, an already-claimed row is left alone.

    Batched like _ensure_manual_tasks; also guarded once-per-login (the missions
    sync used to re-seed all 140 tech tasks a second time after player_info)."""
    if not push_add and client is not None and getattr(client, "_tech_ensured", False):
        return
    _t0 = time.monotonic()
    ids = _tech_task_ids()
    if push_add:
        for tid in ids:
            _accept_manual_task(client, store, commander_id, tid, now,
                                submit=False, push_add=True)
    else:
        _seed_missing_tasks(commander_id, now, ids)
    _ms = (time.monotonic() - _t0) * 1000.0
    log_event("Handbook", "EnsureTech", f"cmd={commander_id} tasks={len(ids)} {_ms:.0f}ms"
              + (" SLOW" if _ms >= 200 else ""),
              LOG_LEVEL_WARN if _ms >= 200 else LOG_LEVEL_DEBUG)
    if client is not None:
        try:
            client._tech_ensured = True
        except Exception:
            pass


def _recompute_milestones(client, store, commander_id, now, push_add=True):
    """Manual unlock milestones (23501-23517) gate individual pages. A milestone
    is satisfied when enough of its target page's sub-tasks have reached their
    target progress. Accept the milestone row (so it can complete later) and, when
    satisfied, auto-complete it so the next page unlocks.

    Batched: milestone 235xx templates whose target_id=0 count across ALL pages
    (sub_type 1011); progress for every referenced sub-task is fetched in one
    query instead of per-milestone scans (this loop was ~170 sequential queries,
    ~2.6s of every login)."""
    from src.answer.task_handlers import _load_task_template

    cfg = _manual_config()
    milestones = sorted(cfg["milestones"])
    if not milestones:
        return

    plans: list[tuple[int, int, list]] = []
    all_subs: set = set()
    for mid in milestones:
        template = _load_task_template(mid)
        if template is None:
            continue
        target_page = int(template.get("target_id", 0) or 0)
        need = int(template.get("target_num", 0) or 0)
        if need <= 0:
            continue
        subs = cfg["page_subtasks"].get(target_page, list(cfg["subtasks"]))
        if not subs:
            continue
        plans.append((mid, need, subs))
        all_subs.update(subs)
    if not plans:
        return

    if push_add:
        # Interactive path (CS_22302): keep per-task accepts so new rows are
        # pushed to the client via TASK_ADD.
        for mid, _need, _subs in plans:
            _accept_manual_task(client, store, commander_id, mid, now,
                                submit=False, push_add=True)
    else:
        have = fetch_existing_task_ids(commander_id, milestones)
        missing = [m for m in milestones if m not in have]
        if missing:
            seed_commander_tasks(commander_id, missing, now)

    prog = fetch_commander_task_progress_map(commander_id, sorted(all_subs))

    for mid, need, subs in plans:
        count = 0
        for tid in subs:
            st = _load_task_template(tid)
            if st is None:
                continue
            tnum = int(st.get("target_num", 0) or 0) or 1
            if prog.get(tid, 0) >= tnum:
                count += 1
        if count >= need:
            _accept_manual_task(client, store, commander_id, mid, now,
                                submit=True, push_add=push_add)
            # The page behind this milestone just unlocked: drop the cached
            # locked-task set so subsequent sync/pushes expose its tasks.
            if client is not None:
                try:
                    client._locked_manual_ids = None
                except Exception:
                    pass


def _push_task_add(client, tid, progress, now, submit_time=0):
    """Hand a task to the client via SC_20003: TaskProxy registers on(20003) ->
    addTask(Task.New(info)) for live task creation. SC_20008 is NOT a push in
    this client build (no on(20008) handler) — it is only the response to a
    CS_20007 accept — so a 20008 "TASK_ADD" push was silently dropped and the
    client never saw the task until the next full 20001 sync.

    submit_time MUST mirror the DB row: 0 for an in-progress task (a non-zero
    value would render it as already claimed on the client), the claim
    timestamp for a force-completed one."""
    ti = protobuf.TASK_ADD(id=tid, progress=progress, accept_time=now, submit_time=submit_time)
    msg = protobuf.SC_20003()
    msg.info.append(ti)
    data = msg.SerializeToString()
    header = generate_packet_header(20003, data, client.packet_index)
    client.write_to_buffer(header + data)


def _build_manual_info_response(client=None):
    """Build SC_22300. The client derives ALL page progress, unlock and finished
    state from this response (top-level finished_task_ids + per-handbook pt/award/
    finished_task_ids), so the server is the single source of truth."""
    response = protobuf.SC_22300()
    try:
        cfg = _manual_config()
    except Exception:
        return response

    commander_id = None
    if client is not None and getattr(client, "commander", None) is not None:
        commander_id = client.commander.commander_id

    finished = set()
    claimed = {}
    if commander_id is not None:
        from src.db.store import get_default_store
        store = get_default_store()
        if store is not None:
            try:
                _ensure_manual_award_table()
                _ensure_manual_tasks(client, store, commander_id, int(time.time()), push_add=False)
                # Possession/state-based sub_tasks (44/85/130/194/211/1011/1013/
                # 1017/1026/1027/403/1050) hold no discrete gameplay event; sync
                # them here so progress is fresh at every login (SC_22300 rides
                # the SC_11003 chain) and every handbook open.
                from src.answer.task_handlers import schedule_possession_sync
                schedule_possession_sync(client)
                if client is not None:
                    try:
                        client._possession_synced = True
                    except Exception:
                        pass
                finished = fetch_submitted_task_ids(
                    commander_id, list(cfg["subtasks"] | cfg["milestones"])
                )
                arows = store.fetch(
                    "SELECT page_id, claimed FROM commander_manual_awards WHERE commander_id=$1",
                    commander_id,
                )
                for r in arows:
                    claimed[r[0]] = r[1]
            except Exception:
                finished = set()
                claimed = {}

    for pid in cfg["pages"]:
        if _page_is_locked(cfg, finished, pid):
            # OMIT locked pages: the client constructs every page present in
            # SC_22300 with isUnlock=true (and ChangeUnlock can only set true),
            # so sending them would unlock the whole handbook at once.
            continue
        subs = cfg["page_subtasks"][pid]
        page_finished = [tid for tid in subs if tid in finished]
        hb = protobuf.TUTHANDBOOK()
        hb.id = pid
        hb.pt = len(page_finished)
        # Clamp award to the page's tier count: a page can only have
        # len(target) pt-award tiers, and the client's
        # CommanderManualPage:GetCurrentPtTarget() indexes target[award]
        # / target[award+1] — an award value larger than the tier list makes
        # it return nil and ShouldShowTip then crashes with
        # "attempt to compare nil with number" (seen after double claims).
        n_tiers = len(cfg["page_targets"].get(pid, {}).get("target", []) or [])
        hb.award = min(claimed.get(pid, 0), n_tiers) if n_tiers else claimed.get(pid, 0)
        for tid in page_finished:
            hb.finished_task_ids.append(tid)
        response.handbooks.append(hb)
    for tid in finished:
        response.finished_task_ids.append(tid)
    try:
        _sent = [h.id for h in response.handbooks]
        log_event("Handbook", "SC_22300",
                  f"cmd={commander_id} pages={len(_sent)}/{len(cfg['pages'])} sent={_sent} "
                  f"finished={len(finished)}",
                  LOG_LEVEL_DEBUG)
    except Exception:
        pass
    return response


def handle_commander_manual_info(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = _build_manual_info_response(client)
    data = response.SerializeToString()
    header = generate_packet_header(22300, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 22300, None


def handle_commander_manual_get_task(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_22302()
        payload.ParseFromString(buffer)
        page_id = int(payload.id)
        index = int(payload.index)
    except Exception:
        page_id = None
        index = None

    if page_id is None:
        return _send_22303(client, 1)

    cfg = _manual_config()
    if page_id not in cfg["page_tasklist"]:
        return _send_22303(client, 1)
    task_list = cfg["page_tasklist"][page_id]
    if index < 0 or index >= len(task_list):
        return _send_22303(client, 1)

    subtask_ids = task_list[index][0]
    store = _default_store_or_fail()
    if store is None:
        return _send_22303(client, 1)

    commander_id = client.commander.commander_id

    # Locked pages must not hand out tasks (client hides them; belt-and-braces).
    req_unlock = list(cfg["page_unlock"].get(page_id, []) or [])
    locked_rows = fetch_submitted_task_ids(commander_id, req_unlock)
    if len(locked_rows) < len(req_unlock):
        return _send_22303(client, 1)

    now = int(time.time())
    for tid in subtask_ids:
        _accept_manual_task(client, store, commander_id, tid, now,
                            submit=False, push_add=True)
    _recompute_milestones(client, store, commander_id, now, push_add=True)
    # SC_22303 response first (the client's callback clears its pending
    # get-task marker on the CURRENT page object), then the SC_22300 refresh
    # so the rebuild carries the newly accepted tasks.
    _send_22303(client, 0)
    _push_manual_refresh(client)
    return 0, 22303, None


def _push_manual_refresh(client: Client):
    try:
        response = _build_manual_info_response(client)
        data = response.SerializeToString()
        header = generate_packet_header(22300, data, client.packet_index)
        client.write_to_buffer(header + data)
    except Exception:
        pass


def handle_commander_manual_get_pt_award(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_22304()
        payload.ParseFromString(buffer)
        page_id = int(payload.id)
    except Exception:
        page_id = None

    if page_id is None:
        return _send_22305(client, 1, [])

    cfg = _manual_config()
    page_cfg = cfg["page_targets"].get(page_id)
    if page_cfg is None:
        return _send_22305(client, 1, [])

    store = _default_store_or_fail()
    if store is None:
        return _send_22305(client, 1, [])

    commander_id = client.commander.commander_id
    try:
        _ensure_manual_award_table()
    except Exception:
        return _send_22305(client, 1, [])

    subs = cfg["page_subtasks"].get(page_id, [])
    sub_rows = fetch_submitted_task_ids(commander_id, list(subs))
    pt = len(sub_rows)

    # Locked pages cannot claim pt awards.
    req_unlock = list(cfg["page_unlock"].get(page_id, []) or [])
    unlock_rows = fetch_submitted_task_ids(commander_id, req_unlock)
    if len(unlock_rows) < len(req_unlock):
        return _send_22305(client, 3, [])

    arow = store.fetchrow(
        "SELECT claimed FROM commander_manual_awards WHERE commander_id=$1 AND page_id=$2",
        commander_id, page_id,
    )
    claimed = int(arow[0]) if arow else 0

    targets = page_cfg["target"]
    drop_client = page_cfg["drop_client"]
    if claimed >= len(targets):
        return _send_22305(client, 2, [])
    if pt < targets[claimed]:
        return _send_22305(client, 3, [])

    drop_list = []
    award = drop_client[claimed] if claimed < len(drop_client) else None
    if award:
        from src.answer.task_handlers import _expand_award_entry, _apply_drops

        for entry in award:
            if len(entry) < 3:
                continue
            dt, di, dc = int(entry[0]), int(entry[1]), int(entry[2])
            for (bt, bi, bc) in _expand_award_entry(dt, di, dc):
                _apply_drops(client, {f"{bt}_{bi}": {"type": bt, "id": bi, "number": bc}})
                drop_list.append(protobuf.DROPINFO(type=bt, id=bi, number=bc))

    store.execute(
        "INSERT INTO commander_manual_awards (commander_id, page_id, claimed) VALUES ($1,$2,1) "
        "ON CONFLICT (commander_id, page_id) DO UPDATE SET claimed = commander_manual_awards.claimed + 1",
        commander_id, page_id,
    )
    # Send the SC_22305 response FIRST. The client's 22305 callback applies
    # the award itself (CommanderManualProxy.AddPageAward -> award = award + 1)
    # and the mediator refreshes the UI. Pushing a full SC_22300 BEFORE the
    # response made the client REBUILD all page objects (proxy on(22300)) and
    # then run AddPageAward on top of the already-up-to-date award value,
    # double-counting it (award > len(target)) -> GetCurrentPtTarget() returned
    # nil -> "attempt to compare nil with number" crash and the claim never
    # displaying as claimed. The client owns the post-claim state update.
    _send_22305(client, 0, drop_list)
    return 0, 22304, None


def _default_store_or_fail():
    from src.db.store import get_default_store
    return get_default_store()


def _send_22303(client: Client, result: int) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_22303()
    response.result = result
    data = response.SerializeToString()
    header = generate_packet_header(22303, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 22303, None


def _send_22305(client: Client, result: int, drop_list) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_22305()
    response.result = result
    for d in (drop_list or []):
        response.drop_list.append(d)
    data = response.SerializeToString()
    header = generate_packet_header(22305, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 22305, None


def handle_commander_guild_technologies(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.answer.guild.public_tech import build_public_guild_tech_response
    response = build_public_guild_tech_response()
    data = response.SerializeToString()
    header = generate_packet_header(62101, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 62101, None


def handle_commander_dock(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_12010()

    commander_id = client.commander.commander_id

    # Passive morale (energy) recovery for ships not in dorm -- see
    # handle_player_dock for the rationale. Covers ships 100+ sent here.
    try:
        import time
        from src.orm.morale import apply_commander_morale_recovery
        apply_commander_morale_recovery(commander_id, int(time.time()))
    except Exception:
        pass

    try:
        rows = list_dock_ships(commander_id)
    except Exception as e:
        return 0, 12010, e

    if len(rows) > 100:
        rows = rows[100:]
    from src.orm.game_data import preload_ship_template_configs
    preload_ship_template_configs([r.ship_id for r in rows])

    # SHIPINFO snapshot building lives in ONE place
    # (src/answer/shipinfo/builder.py) — same fields as the login SC_12001
    # dock sync: skills, equip slots (count from the ship template config),
    # strengths, transforms, shadows, flag phantoms.
    from src.answer.shipinfo.builder import build_ship_infos
    for s in build_ship_infos(rows, commander_id):
        response.ship_list.append(s)

    data = response.SerializeToString()
    header = generate_packet_header(12010, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 12010, None


def handle_commander_commissions_fleet(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.orm.daily_level import get_daily_level_counts, list_daily_quick_stages
    from src.orm.daily_expedition import (
        get_elite_expedition_count,
        get_escort_expedition_count,
        get_chapter_defeat_counts,
    )
    response = protobuf.SC_13201()
    try:
        commander_id = client.commander.commander_id
        counts = get_daily_level_counts(commander_id)
        for daily_level_id, count in counts.items():
            entry = protobuf.EXPEDITION_DAILY_COUNT()
            entry.id = daily_level_id
            entry.count = count
            response.count_list.append(entry)
        for stage_id in list_daily_quick_stages(commander_id):
            response.quick_expedition_list.append(stage_id)
        response.elite_expedition_count = get_elite_expedition_count(commander_id)
        response.escort_expedition_count = get_escort_expedition_count(commander_id)
        for chapter_id, count in get_chapter_defeat_counts(commander_id).items():
            entry = protobuf.EXPEDITION_DAILY_COUNT()
            entry.id = chapter_id
            entry.count = count
            response.chapter_count_list.append(entry)
    except Exception as e:
        return 0, 13201, e
    data = response.SerializeToString()
    header = generate_packet_header(13201, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 13201, None
