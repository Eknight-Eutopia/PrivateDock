import datetime
import heapq
import random
from typing import Optional

from sqlalchemy import text as _sql_text

from src.config.game_variables import (
    get_build_dock_slots,
    get_build_time_multiplier,
    get_default_build_time_seconds,
)
from src.consts.build import MAX_BUILD_WORK_COUNT
from src.db.store import get_default_store
from src.orm.commander import (
    aget_commander_build_counts,
    aincrement_commander_build_counts,
)

# How many constructions may count down at the same time (the client's "work
# slots"). Configured in configurations/game_variables.json (build_dock_slots).
BUILD_DOCK_SLOTS = get_build_dock_slots()
_LAST_LOADED_DOCK_SLOTS = BUILD_DOCK_SLOTS


def _current_dock_slots() -> int:
    """Return the current dock slot count, syncing with config or module overrides."""
    cfg_slots = get_build_dock_slots()
    mod_slots = globals().get("BUILD_DOCK_SLOTS")
    if mod_slots is not None and mod_slots != globals().get("_LAST_LOADED_DOCK_SLOTS", cfg_slots):
        return mod_slots
    globals()["_LAST_LOADED_DOCK_SLOTS"] = cfg_slots
    globals()["BUILD_DOCK_SLOTS"] = cfg_slots
    return cfg_slots

# Total dock capacity (client const.lua MAX_BUILD_WORK_COUNT = 10): how many
# builds (running + queued) the dock may hold at all. Wishing-well draws gate on
# this, mirroring the client's canBuildShipByBuildId check. The value itself is
# imported from src.consts.build at the top of this module.

# builds.state column values:
BUILD_STATE_QUEUED = 0    # waiting for a free dock slot (finishes_at = planned finish)
BUILD_STATE_STARTED = 1   # started: running (finishes_at in future) or finished (in past)

DEFAULT_BUILD_TIME = 600


def ordered_builds(builds: list) -> list:
    return sorted(builds, key=lambda b: b["id"])


def remaining_seconds(finish_time: datetime.datetime, now: datetime.datetime) -> int:
    remaining = (finish_time - now).total_seconds()
    return max(0, int(remaining))


def _as_utc(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        try:
            return dt.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            return None
    return dt


# ─────────────────────────────────────────────────────────────────────────────
# 4-slot build queue (pure core, unit-testable)
# ─────────────────────────────────────────────────────────────────────────────
def settle_build_queue(builds: list, durations: dict, now: datetime.datetime) -> list:
    """Assign every build an authoritative ``state``/``finishes_at``.

    ``builds`` is the commander's full worklist in creation (id) order, each an
    in-place dict with ``id``, ``ship_id``, ``pool_id``, ``state`` and
    ``finishes_at``. ``durations`` maps ship_id -> build seconds. The list is
    mutated and returned.

    Model (mirrors the client's own chain - `BuildShipProxy.setBuildShipState`
    + `activeNextBuild`): at most ``BUILD_DOCK_SLOTS`` constructions tick at
    once; a build that is queued when all slots are busy starts ticking at the
    moment a running build's countdown completes, in FIFO order, for its full
    build time. State is persistent so re-settles are stable:
      1. legacy reconciliation - never leave more than BUILD_DOCK_SLOTS ticking
         (older rows started before this rule: the extra ones are re-queued and
         forfeit their partial progress),
      2. promote queued builds whose scheduled start (finishes_at - duration)
         has passed (the queue advanced while nobody was looking),
      3. schedule every remaining queued build on the slot-free timeline.
    """
    now = _as_utc(now) or datetime.datetime.now(datetime.timezone.utc)
    for b in builds:
        b["state"] = int(b.get("state", BUILD_STATE_STARTED))
        b["finishes_at"] = _as_utc(b.get("finishes_at"))
        # started rows must carry a finish; treat orphans as queued.
        if b["state"] == BUILD_STATE_STARTED and b["finishes_at"] is None:
            b["state"] = BUILD_STATE_QUEUED

    # 1. never more than dock_slots ticking at once (legacy reconciliation)
    slots = _current_dock_slots()
    ticking = [b for b in builds
               if b["state"] == BUILD_STATE_STARTED and b["finishes_at"] > now]
    if len(ticking) > slots:
        keep = set(id(b) for b in
                   sorted(ticking, key=lambda b: b["finishes_at"])[:slots])
        for b in ticking:
            if id(b) not in keep:
                b["state"] = BUILD_STATE_QUEUED
                b["finishes_at"] = None

    # 2. promote queued builds whose scheduled start has arrived
    for b in builds:
        if b["state"] != BUILD_STATE_QUEUED or b["finishes_at"] is None:
            continue
        dur_val = durations.get(b["ship_id"])
        dur = int(dur_val if dur_val is not None else round(get_default_build_time_seconds() * get_build_time_multiplier()))
        if b["finishes_at"] - datetime.timedelta(seconds=dur) <= now:
            b["state"] = BUILD_STATE_STARTED

    # 3. schedule the rest on the FIFO timeline. Slots are anonymous: each
    #    ticking build releases its slot at its finish; unused slots are free now.
    heap = [b["finishes_at"].timestamp()
            for b in builds
            if b["state"] == BUILD_STATE_STARTED and b["finishes_at"] > now]
    free_now = slots - len(heap)
    for _ in range(max(0, free_now)):
        heap.append(now.timestamp())
    heapq.heapify(heap)
    for b in builds:
        if b["state"] != BUILD_STATE_QUEUED:
            continue
        dur_val = durations.get(b["ship_id"])
        dur = int(dur_val if dur_val is not None else round(get_default_build_time_seconds() * get_build_time_multiplier()))
        start_ts = heapq.heappop(heap)
        start = datetime.datetime.fromtimestamp(start_ts, datetime.timezone.utc)
        finish = start + datetime.timedelta(seconds=max(0, dur))
        b["finishes_at"] = finish
        if start <= now:
            # the slot is free right now: it is already ticking.
            b["state"] = BUILD_STATE_STARTED
        heapq.heappush(heap, finish.timestamp())
    return builds


# ─────────────────────────────────────────────────────────────────────────────
# Sync DB wrappers (used by the draw / sync / quick-finish handlers)
# ─────────────────────────────────────────────────────────────────────────────
def _parse_row_finish(value):
    if isinstance(value, str):
        from src.db import sqlite_types
        parsed = sqlite_types._convert_timestamp(value)
        return parsed
    return value


# Guide handbook task "Build 1 ship." (type 17, sub_type 30, auto_commit=1):
# the server auto-confirms it on the tutorial build, so its unsubmitted state
# marks "no tutorial build yet".
TUTORIAL_FIRST_BUILD_TASK_ID = 23003


def is_before_first_build_sync(commander_id: int) -> bool:
    """True until the tutorial build's auto-commit task (Guide "Build 1 ship.",
    task 23003) is submitted in commander_tasks."""
    store = get_default_store()
    if store is None:
        return False
    row = store.fetchrow(
        "SELECT submit_time FROM commander_tasks WHERE commander_id = $1 AND task_id = $2",
        commander_id, TUTORIAL_FIRST_BUILD_TASK_ID,
    )
    return row is None or int(row[0] or 0) == 0


def load_build_rows_sync(commander_id: int, session) -> list:
    rows = session.execute(_sql_text(
        "SELECT b.id, b.ship_id, b.pool_id, b.finishes_at, b.state, "
        "COALESCE(s.build_time, 600) AS duration "
        "FROM builds b LEFT JOIN ships s ON s.template_id = b.ship_id "
        "WHERE b.builder_id = :cid ORDER BY b.id"
    ), {"cid": commander_id}).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": int(r[0]),
            "ship_id": int(r[1]),
            "pool_id": int(r[2]),
            "finishes_at": _as_utc(_parse_row_finish(r[3])),
            "state": (int(r[4]) if r[4] is not None else BUILD_STATE_STARTED),
            "duration": int(r[5]) if r[5] is not None else get_default_build_time_seconds(),
        })
    return out


def _persist_build_rows_sync(session, rows):
    """Write changed state/finishes_at back for already-existing rows."""
    for b in rows:
        if b.get("_new"):
            continue
        session.execute(_sql_text(
            "UPDATE builds SET state = :st, finishes_at = :fa WHERE id = :id"
        ), {"st": b["state"], "fa": b["finishes_at"], "id": b["id"]})


def settle_commander_builds_sync(commander_id: int,
                                 now: Optional[datetime.datetime] = None) -> list:
    """Settle a commander's whole worklist against the 4-slot queue and persist
    the authoritative state. Returns the authoritative rows (id order)."""
    from src.db.session import get_sync_session
    now = _as_utc(now) or datetime.datetime.now(datetime.timezone.utc)
    with get_sync_session() as session:
        rows = load_build_rows_sync(commander_id, session)
        durations = {b["ship_id"]: b["duration"] for b in rows}
        # capture pre-settle state so we only persist actual changes
        before = {(b["id"],) : (b["state"], b["finishes_at"]) for b in rows}
        settle_build_queue(rows, durations, now)
        changed = [b for b in rows
                   if before.get((b["id"],)) != (b["state"], b["finishes_at"])]
        if changed:
            _persist_build_rows_sync(session, changed)
            session.commit()
        return rows


def plan_builds_sync(commander_id: int, draws: list,
                     now: Optional[datetime.datetime] = None):
    """Insert ``draws`` (list of ``{ship_id, pool_id}``, in draw order) into the
    4-slot build queue. Returns ``(all_rows, new_rows)``: the commander's full
    authoritative worklist (id order) and the newly-created rows with their real
    ids, ``state``/``finishes_at``/``duration`` for the SC_12003/SC_11203
    payloads. Every existing row is settled and persisted too."""
    from src.db.session import get_sync_session
    now = _as_utc(now) or datetime.datetime.now(datetime.timezone.utc)
    with get_sync_session() as session:
        rows = load_build_rows_sync(commander_id, session)
        durations = {b["ship_id"]: b["duration"] for b in rows}

        for _draw in draws:
            ship_id = int(_draw["ship_id"])
            pool_id = int(_draw["pool_id"])
            if ship_id not in durations:
                row = session.execute(_sql_text(
                    "SELECT COALESCE(build_time, 600) FROM ships WHERE template_id = :sid"
                ), {"sid": ship_id}).fetchone()
                base_time = int(row[0]) if row and row[0] is not None else get_default_build_time_seconds()
                durations[ship_id] = int(round(base_time * get_build_time_multiplier()))
            rows.append({
                # placeholder ids keep the draw order; real ids come from INSERT
                "id": -(len(rows) + 1),
                "ship_id": ship_id,
                "pool_id": pool_id,
                "finishes_at": None,
                "state": BUILD_STATE_QUEUED,
                "duration": durations[ship_id],
                "_new": True,
            })

        before = {(b["id"],): (b["state"], b["finishes_at"])
                  for b in rows if not b.get("_new")}
        settle_build_queue(rows, durations, now)
        changed = [b for b in rows
                   if not b.get("_new")
                   and before.get((b["id"],)) != (b["state"], b["finishes_at"])]
        if changed:
            _persist_build_rows_sync(session, changed)

        new_rows = []
        for b in rows:
            if not b.get("_new"):
                continue
            inserted = session.execute(_sql_text(
                "INSERT INTO builds (builder_id, ship_id, pool_id, finishes_at, state) "
                "VALUES (:cid, :sid, :pid, :fa, :st) RETURNING id"
            ), {"cid": commander_id, "sid": b["ship_id"], "pid": b["pool_id"],
                "fa": b["finishes_at"], "st": b["state"]}).fetchone()
            b["id"] = int(inserted[0]) if inserted else b["id"]
            b.pop("_new", None)
            new_rows.append(b)
        session.commit()
        return rows, new_rows


# ─────────────────────────────────────────────────────────────────────────────
# Existing async helpers (draw-count bookkeeping, list queries)
# ─────────────────────────────────────────────────────────────────────────────
async def get_random_pool_ship(pool_id: int) -> Optional[dict]:
    random_n = random.randint(1, 100)
    if random_n <= 7:
        rarity = 5
    elif random_n <= 19:
        rarity = 4
    elif random_n <= 70:
        rarity = 3
    else:
        rarity = 2
    store = get_default_store()
    # Membership via build_pool_ships (multi-pool capable); ships.pool_id was
    # dropped (migration 0095).
    rows = await store.afetch(
        "SELECT s.template_id, s.name, s.english_name, s.rarity_id, s.star, "
        "s.type, s.nationality, s.build_time "
        "FROM build_pool_ships b JOIN ships s ON s.template_id = b.template_id "
        "WHERE b.pool_id = $1 AND s.rarity_id = $2 ORDER BY RANDOM() LIMIT 1",
        pool_id, rarity,
    )
    if rows:
        return dict(rows[0])
    return None


async def create_build(commander_id: int, pool_id: int, ship_id: int, finishes_at: datetime.datetime) -> Optional[int]:
    store = get_default_store()
    row = await store.afetchrow(
        "INSERT INTO builds (builder_id, ship_id, pool_id, finishes_at) VALUES ($1, $2, $3, $4) RETURNING id",
        commander_id, ship_id, pool_id, finishes_at,
    )
    return row["id"] if row else None


async def list_builds_range(commander_id: int, offset: int, limit: int) -> list:
    store = get_default_store()
    rows = await store.afetch(
        "SELECT id, builder_id, ship_id, pool_id, finishes_at, state FROM builds "
        "WHERE builder_id = $1 ORDER BY id ASC OFFSET $2 LIMIT $3",
        commander_id, offset, limit,
    )
    return [dict(r) for r in rows]


async def list_all_builds(commander_id: int) -> list:
    store = get_default_store()
    rows = await store.afetch(
        "SELECT id, builder_id, ship_id, pool_id, finishes_at, state FROM builds "
        "WHERE builder_id = $1 ORDER BY id ASC",
        commander_id,
    )
    return [dict(r) for r in rows]


async def update_build_finish_time(build_id: int, finishes_at: datetime.datetime):
    store = get_default_store()
    await store.aexecute(
        "UPDATE builds SET finishes_at = $2 WHERE id = $1",
        build_id, finishes_at,
    )


async def delete_build(build_id: int):
    store = get_default_store()
    await store.aexecute("DELETE FROM builds WHERE id = $1", build_id)


async def get_commander_counts(commander_id: int) -> dict:
    return await aget_commander_build_counts(commander_id)


async def increment_draw_count(commander_id: int, count: int):
    await aincrement_commander_build_counts(commander_id, count)
