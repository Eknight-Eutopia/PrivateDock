import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.logger.logger import log_event, LOG_LEVEL_DEBUG, LOG_LEVEL_WARN
from src.db.store import get_default_store
from src.orm.commander_task import (
    create_or_accept_task,
    fetch_all_commander_tasks,
    fetch_commander_tasks,
    fetch_commander_task_progress_map,
    fetch_existing_task_ids,
    get_commander_task_submit_time,
    upsert_task_progress_least,
)
from src.orm.weekly_task_progress import (
    aload_weekly_state,
    asave_weekly_state,
    load_weekly_state,
    save_weekly_state,
)
from src.orm.config_entry import get_config_entry_sync, list_config_entries_sync
from src.shopreset.framework import daily_window

RESULT_SUCCESS = 0
RESULT_FAILED = 1
QUICK_TASK_PASS_TICKET_ID = 15013


_ALL_TASK_TEMPLATES_CACHE: Optional[dict[int, dict]] = None


def _all_task_templates() -> dict[int, dict]:
    """All task_data_template entries keyed by id, loaded in ONE fast raw query.

    Uses raw SQL + orjson instead of SQLAlchemy ORM entity mapping to avoid
    instantiating ~10k Python model objects. The map is cached process-wide."""
    global _ALL_TASK_TEMPLATES_CACHE
    if _ALL_TASK_TEMPLATES_CACHE is not None:
        return _ALL_TASK_TEMPLATES_CACHE
    mapping: dict[int, dict] = {}
    try:
        try:
            import orjson
            _loads = orjson.loads
        except ImportError:
            _loads = json.loads
        from src.db.session import get_sync_session
        from sqlalchemy import text
        with get_sync_session() as session:
            rows = session.execute(
                text("SELECT key, data FROM config_entries WHERE category = :cat"),
                {"cat": "sharecfgdata/task_data_template.json"},
            ).fetchall()
        for k, raw in rows:
            d = raw if isinstance(raw, dict) else _loads(raw)
            if isinstance(d, dict) and d.get("id") is not None:
                try:
                    mapping[int(d["id"])] = d
                except (TypeError, ValueError):
                    continue
    except Exception:
        pass
    _ALL_TASK_TEMPLATES_CACHE = mapping
    return mapping


def _load_task_template(task_id: int) -> Optional[dict]:
    tid = int(task_id)
    all_map = _all_task_templates()
    if tid in all_map:
        return all_map[tid]
    entry = get_config_entry_sync("sharecfgdata/task_data_template.json", str(tid))
    if entry is None:
        return None
    if isinstance(entry.data, str):
        return json.loads(entry.data)
    return entry.data


def _build_task_drops(template: dict) -> dict:
    drops = {}
    award_display = template.get("award_display", [])
    if isinstance(award_display, list):
        for entry in award_display:
            if len(entry) >= 3:
                for (t, i, c) in _expand_award_entry(entry[0], entry[1], entry[2]):
                    _accumulate_drop(drops, t, i, c)
    return drops


def _accumulate_drop(drops: dict, drop_type: int, drop_id: int, count: int):
    key = f"{drop_type}_{drop_id}"
    if key in drops:
        existing = drops[key]
        existing["number"] = existing.get("number", 0) + count
    else:
        drops[key] = {"type": drop_type, "id": drop_id, "number": count}


def _expand_award_entry(drop_type: int, drop_id: int, count: int) -> list:
    """Expand one award_display entry into concrete (type, id, count) entries.

    Mystery virtual items (Mystery Tech/Gear Parts, config types 98/99 with a
    non-empty display_icon pool) are resolved into their random contents so the
    reward popup and the bag both show REAL items, never an unopenable wrapper
    (e.g. "T4 Mystery Tech Pack" id=54034 -> a concrete T4 Tech Pack). Without
    this, the client popup shows the mystery name while the bag may end up with
    nothing usable.
    """
    if drop_type == 2:
        from src.orm.item import resolve_virtual_item_drops
        return resolve_virtual_item_drops(drop_id, count)
    return [(drop_type, drop_id, count)]


def _drop_map_to_sorted_list(drops: dict) -> list:
    result = []
    for key in sorted(drops.keys()):
        d = drops[key]
        from src.protobuf import protobuf
        result.append(protobuf.DROPINFO(type=d["type"], id=d["id"], number=d["number"]))
    return result


def _apply_drops(client: Client, drops: dict):
    commander = client.commander
    if commander is None:
        return
    for key, d in drops.items():
        if d["type"] == 1:
            commander.add_resource(d["id"], d["number"])
        elif d["type"] == 2:
            commander.add_item(d["id"], d["number"])
        elif d["type"] == 3:
            pass
        elif d["type"] == 4:
            commander.add_ship(d["id"])
        elif d["type"] == 5:
            commander.give_skin(d["id"])
        elif d["type"] == 6:
            pass
        elif d["type"] == 7:
            pass
        elif d["type"] == 8:
            commander.add_item(d["id"], d["number"])
        elif d["type"] == 9:
            pass
        elif d["type"] == 10:
            pass
        elif d["type"] == 11:
            pass
        elif d["type"] == 12:
            pass
        elif d["type"] == 13:
            pass
        elif d["type"] in (14, 15, 31):
            from src.orm.commander_attire import grant_commander_attire_drop_sync
            grant_commander_attire_drop_sync(commander.commander_id, d["type"], d["id"], d["number"])
        elif d["type"] == 16:
            pass
        elif d["type"] == 17:
            pass
        elif d["type"] == 18:
            pass
        elif d["type"] == 19:
            pass
        elif d["type"] == 20:
            pass


def _maybe_accept_mingshi_next_task(client: Client, task_id: int):
    """Akashi's Commission chain (activity 21, tasks 5001-5020, story_icon
    "mingshi"): the client never advances next_task itself, so a successful
    claim of one commission accepts the next one and pushes TASK_ADD — that is
    what keeps the chain running to the final Akashi ship reward.

    Skips forward over already-submitted links (legacy/batch-claimed rows can
    leave gaps) and stops at a task that is in progress or missing from the
    config; nothing is pushed for links that already have a row."""
    try:
        template = _load_task_template(task_id)
        if template is None or template.get("story_icon") != "mingshi":
            return
        store = get_default_store()
        if store is None or client is None:
            return
        commander_id = client.commander.commander_id
        now = int(time.time())

        def _next_of(tid):
            try:
                return int((_load_task_template(tid) or {}).get("next_task", 0) or 0)
            except (TypeError, ValueError):
                return 0

        tid = task_id
        seen = set()
        while tid > 0 and tid not in seen:
            seen.add(tid)
            nxt = _next_of(tid)
            if nxt <= 0 or _load_task_template(nxt) is None:
                return
            submit_time = get_commander_task_submit_time(commander_id, nxt)
            if submit_time is None:
                create_or_accept_task(commander_id, nxt, now)
                from src.answer.commandermisc.handlers import _push_task_add
                _push_task_add(client, nxt, 0, now)
                return
            if not submit_time:
                return  # next link already accepted and in progress
            # Already claimed -> keep walking forward. With a strictly
            # sequential chain this only happens if the row was force-completed
            # by something else (the questline must be done in order per the
            # wiki), so make it visible instead of silently skipping tasks.
            from src.logger.logger import log_event, LOG_LEVEL_WARN
            log_event("Tasks", "MingshiChain",
                      f"cmd={commander_id}: commission {nxt} already claimed while "
                      f"walking from {task_id} - force-completed row?",
                      LOG_LEVEL_WARN)
            tid = nxt
    except Exception as e:
        from src.logger.logger import log_event, LOG_LEVEL_ERROR
        log_event("Tasks", "MingshiChain",
                  f"failed to hand out next commission after task {task_id}: {e}",
                  LOG_LEVEL_ERROR)


# Task types the server tracks without an explicit accept: main (1), branch/
# star (2), daily (3), weekly (4), new-weekly (13). Event-family types (5
# hidden/Akashi, 6 ACTIVITY, 15 REFLUX, 16 ACTIVITY_REPEAT, 26 ACTIVITY_BRANCH
# "Side", 36 ACTIVITY_ROUTINE event dailies, ...) exist only while their event
# granted them -- a generic battle event must never conjure rows for every old
# event's tasks (that is how hundreds of dead Side/Daily missions appeared).
SERVER_TRACKED_TASK_TYPES = {1, 2, 3, 4, 13}


def _submit_task_and_get_drops(client: Client, task_id: int, template: dict, ticket_cost: int) -> tuple[Optional[dict], bool]:
    if template is None:
        return None, False

    drops = _build_task_drops(template)
    store = get_default_store()
    if store is None:
        return None, False

    commander_id = client.commander.commander_id
    now = int(__import__("time").time())

    try:
        task = store.fetchrow(
            "SELECT task_id, progress, submit_time FROM commander_tasks WHERE commander_id = $1 AND task_id = $2",
            commander_id, task_id,
        )

        if task is not None and task[2] != 0:
            return None, False

        if ticket_cost > 0:
            if not client.commander.has_enough_item(QUICK_TASK_PASS_TICKET_ID, ticket_cost):
                return None, False
            client.commander.consume_item(QUICK_TASK_PASS_TICKET_ID, ticket_cost)
            store.execute(
                "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
                "VALUES ($1, $2, $3, $4, 0) "
                "ON CONFLICT (commander_id, task_id) DO UPDATE SET progress = EXCLUDED.progress",
                commander_id, task_id, template.get("target_num", 0), now,
            )
            task = store.fetchrow(
                "SELECT task_id, progress, submit_time FROM commander_tasks WHERE commander_id = $1 AND task_id = $2",
                commander_id, task_id,
            )

        if task is None:
            task = type("Row", (), {"__getitem__": lambda _s, i: [task_id, 0, 0][i]})()

        target_num = template.get("target_num", 0)
        sub_type = int(template.get("sub_type", 0) or 0)
        give_target = _coerce_int(template.get("target_id", 0), 0)
        auto_commit = int(template.get("auto_commit", 0) or 0)
        # NOTE: keep the GIVE_ITEM ownership gate FIRST so a real consume is never
        # bypassed, then trust the client for auto_commit tasks.
        # TASK_SUB_TYPE_GIVE_ITEM (1000): complete by owning the items. The client
        # consumes them only after the server returns success, so gate on ownership
        # rather than the (often untracked) progress counter.
        if sub_type == 1000 and give_target > 0 and target_num > 0:
            if not client.commander.has_enough_item(give_target, target_num):
                return None, False
        elif sub_type == 1002 and give_target > 0 and target_num > 0:
            # Dev Dock "Hull Construction" missions (TASK_SUB_TYPE_PLAYER_RES,
            # e.g. "gather 20,000 coins"): the client renders progress from the
            # current resource balance, so gate on holding the amount. Nothing is
            # consumed -- only hidden type-8 shipyard chain missions use 1002.
            if not client.commander.has_enough_resource(give_target, target_num):
                return None, False
        elif auto_commit == 1:
            # Guide / Commander-Manual auto-commit tasks (230xx, type 17 with
            # auto_commit=1): the client auto-claims them the moment its own
            # isFinish() becomes true, even when the on-server progress row trails
            # or was never emitted for a tutorial action (these use a wide range of
            # sub_types: 1011 "reach level", 30 "build", 31 "sortie", etc.). Trust
            # the client and accept the submit instead of gating on the server-side
            # progress counter, which otherwise toasts "Failed to submit mission:
            # 1:Invalid Input." on every fresh login. (The older sub_type 2000-3000
            # branch below covered only tutorial UI-trigger tasks.)
            pass
        elif sub_type == 1050 and int(template.get("type", 0) or 0) == 9:
            # Dev Dock (ShipBluePrint) faction-tech prerequisite tasks
            # (TASK_SUB_TYPE_TECHNOLOGY_POINT): the client renders the progress
            # bar from its own fleet-tech mirror (collection + fleet_tech_ship_template)
            # and auto-submits once it is full; accept only when the server-side
            # faction points (same data and formula) actually reach the target.
            from src.answer.shipyard_blueprint_helpers import compute_faction_tech_points
            try:
                nation = int(str(give_target or 0))
            except (TypeError, ValueError):
                nation = 0
            pts_map = compute_faction_tech_points(client.commander.commander_id)
            if int(pts_map.get(nation, 0) or 0) < target_num:
                return None, False
        elif sub_type == 1021 and give_target > 0 and target_num > 0:
            # Chapter "Get 3 stars in stage X-Y" missions (branch type-2) --
            # the official one-time 3-Star Reward. The bar is filled only by
            # server paths that verified the chapter state (battle emit, or
            # login prefill from the star_rewarded marker / star counters), and
            # the chapter state only ever grows, so a submit is accepted when
            # the stage's stars are really on record.
            if not _chapter_star_completed(commander_id, give_target):
                return None, False
        elif sub_type == 1020 and give_target > 0 and target_num > 0 and int(template.get("type", 0) or 0) == 1:
            # Scenario "Clear X-Y" missions (first-clear reward): only
            # claimable once the stage's first full clear is on record.
            if not _chapter_cleared(commander_id, give_target):
                return None, False
        elif 2000 <= sub_type < 3000:
            # Client-trigger tasks (guide/tutorial UI actions such as 23034
            # "check the morale icon"): the client is authoritative -- its
            # Task:getProgress() defaults to target_num for these sub_types, so
            # it auto-submits them at the main menu (TaskProxy.pushAutoSubmit
            # Task) even when no CS_20016 event ever advanced the server row.
            # Rejecting them made the client toast "Failed to submit mission:
            # 1:Invalid Input." on every login.
            pass
        elif target_num > 0 and task[1] < target_num:
            return None, False

        if task is None:
            # No row existed (e.g. a client-trigger/give-item submit for a task
            # that was never accepted): record it as submitted so the client's
            # task sync shows it claimed and the submit cannot repeat.
            store.execute(
                "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
                "VALUES ($1, $2, $3, $4, $5) "
                "ON CONFLICT (commander_id, task_id) DO NOTHING",
                commander_id, task_id, target_num, now, now,
            )
        else:
            store.execute(
                "UPDATE commander_tasks SET submit_time = $1 WHERE commander_id = $2 AND task_id = $3 AND submit_time = 0",
                now, commander_id, task_id,
            )

        # The client's SubmitTaskCommand.CheckTaskSub consumes the mission's
        # goods locally right after SC_20006 result==0 (GIVE_ITEM -> bag items,
        # PLAYER_RES -> wallet). Mirror that on the server so the DB matches the
        # client cache: e.g. the Dev Dock "Design Breakthrough" (10 retrofit
        # blueprints) and "Hull Construction" stages (20k coins / 5 cubes) are
        # actually spent when handed in.
        if sub_type == 1000 and give_target > 0 and target_num > 0:
            client.commander.consume_item(give_target, target_num)
        elif sub_type == 1002 and give_target > 0 and target_num > 0:
            client.commander.consume_resource(give_target, target_num)

        _apply_drops(client, drops)

        # Server-authoritative task progress: task completion events (e.g.
        # sub_type 91 "Complete task target_id N times" like Akashi 5006,
        # sub_type 90 "Complete tasks from target_id list" like 7211,
        # sub_type 99 "Complete development/board missions").
        try:
            schedule_emit(client, 91, task_id, 1)
            schedule_emit(client, 90, task_id, 1)
            schedule_emit(client, 99, task_id, 1)
        except Exception:
            pass
    except Exception:
        return None, False

    return drops, True


def _send_message(client: Client, packet_id: int, message) -> tuple[int, int, Optional[Exception]]:
    data = message.SerializeToString()
    header = generate_packet_header(packet_id, data, client.packet_index)
    client.write_to_buffer(header + data)
    return len(data), packet_id, None


_MAIN_TASK_IDS_CACHE = None

def _get_main_task_ids() -> list:
    global _MAIN_TASK_IDS_CACHE
    if _MAIN_TASK_IDS_CACHE is not None:
        return _MAIN_TASK_IDS_CACHE
    ids = []
    try:
        all_tpls = _all_task_templates()
        for tid, d in all_tpls.items():
            if isinstance(d, dict) and d.get("type") == 1:
                ids.append(int(tid))
    except Exception:
        pass
    ids.sort()
    _MAIN_TASK_IDS_CACHE = ids
    return ids


_DAILY_TASK_IDS_CACHE = None

def _get_daily_task_ids() -> list:
    global _DAILY_TASK_IDS_CACHE
    if _DAILY_TASK_IDS_CACHE is not None:
        return _DAILY_TASK_IDS_CACHE
    ids = []
    entry = get_config_entry_sync("ShareCfg/gameset.json", "daily_task_new")
    if entry is not None:
        data = entry.data
        if isinstance(data, str):
            data = json.loads(data)
        desc = data.get("description", []) if isinstance(data, dict) else []
        if isinstance(desc, list):
            ids.extend(int(x) for x in desc)
    try:
        tpls = _all_task_templates()
        for tid, t in tpls.items():
            if isinstance(t, dict) and t.get("type") == 3:
                itid = int(tid)
                if itid not in ids:
                    ids.append(itid)
    except Exception:
        for extra_id in (7210, 7211):
            if extra_id not in ids:
                ids.append(extra_id)
    _DAILY_TASK_IDS_CACHE = ids
    return ids


_STAR_TASK_IDS_CACHE = None

def _get_star_task_ids() -> list:
    """Official "Get 3 stars in stage X-Y" missions (branch type-2, sub_type
    1021; EN ids start at 3001 and cover the normal campaign 101-1604 plus the
    hard-mode chapters 10101+). These ARE the official one-time 3-Star Reward
    for each stage."""
    global _STAR_TASK_IDS_CACHE
    if _STAR_TASK_IDS_CACHE is not None:
        return _STAR_TASK_IDS_CACHE
    ids = []
    try:
        all_tpls = _all_task_templates()
        for tid, d in all_tpls.items():
            if isinstance(d, dict) and d.get("type") == 2 and d.get("sub_type") == 1021:
                ids.append(int(tid))
    except Exception:
        pass
    ids.sort()
    _STAR_TASK_IDS_CACHE = ids
    return ids


_STAR_CHAPTER_TPL_CACHE: dict = {}


def _chapter_star_template(chapter_id: int) -> Optional[dict]:
    """chapter_template.json entry for a stage (cached); None when missing."""
    global _STAR_CHAPTER_TPL_CACHE
    if chapter_id in _STAR_CHAPTER_TPL_CACHE:
        return _STAR_CHAPTER_TPL_CACHE[chapter_id]
    data = None
    entry = get_config_entry_sync("sharecfgdata/chapter_template.json", str(chapter_id))
    if entry is not None:
        data = entry.data
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = None
    if not isinstance(data, dict):
        data = None
    _STAR_CHAPTER_TPL_CACHE[chapter_id] = data
    return data


def _counters_satisfy_stars(counts, template) -> bool:
    """Mirror of battle_session._all_star_objectives_complete over the recorded
    star counters: every objective (star_require_i with num_i > 0) satisfied.
    Condition types 4/5 (single-clear constraints) are met after one qualifying
    clear (count >= 1); the others require count >= num. Counters accumulate
    per stage and never reset, so they are the durable record of stars earned
    even for stages cleared before the star-tracking columns existed."""
    if not counts or not template:
        return False
    for i, count in enumerate(counts):
        star_type = template.get("star_require_%d" % (i + 1), 0) or 0
        if not star_type:
            continue
        num = template.get("num_%d" % (i + 1), 0) or 0
        if star_type in (4, 5):
            achieved = count >= 1
        else:
            achieved = count >= num
        if not achieved:
            return False
    return True


def _chapter_progress_state(commander_id: int) -> dict:
    """chapter_id -> {"star": star_rewarded, "pass": pass_count,
    "counts": (kill_boss, kill_enemy, take_box)} from chapter_progress.
    "star" marks a stage whose 3-star completion the battle path recorded;
    pass_count >= 1 marks a stage cleared at least once. Read-only; missing
    table -> {}."""
    store = get_default_store()
    out: dict = {}
    if store is None:
        return out
    try:
        rows = store.fetch(
            "SELECT chapter_id, star_rewarded, pass_count, "
            "kill_boss_count, kill_enemy_count, take_box_count "
            "FROM chapter_progress WHERE commander_id = $1",
            commander_id,
        )
    except Exception:
        return out
    for r in rows:
        try:
            out[int(r[0])] = {
                "star": int(r[1] or 0),
                "pass": int(r[2] or 0),
                "counts": (int(r[3] or 0), int(r[4] or 0), int(r[5] or 0)),
            }
        except (TypeError, ValueError):
            continue
    return out


def _chapter_star_completed(commander_id: int, chapter_id: int) -> bool:
    """True when the stage's 3 stars are earned: either recorded by the battle
    path (star_rewarded) or derivable from the persisted star counters against
    the chapter template (covers stages 3-starred before the tracking columns
    existed, which no later battle would re-flag)."""
    state = _chapter_progress_state(commander_id)
    info = state.get(int(chapter_id))
    if info is None:
        return False
    if info["star"] == 1:
        return True
    return _counters_satisfy_stars(info["counts"], _chapter_star_template(int(chapter_id)))


def _chapter_cleared(commander_id: int, chapter_id: int) -> bool:
    state = _chapter_progress_state(commander_id)
    return state.get(int(chapter_id), {}).get("pass", 0) >= 1


def _ensure_star_tasks(store, commander_id: int):
    """Seed the official "Get 3 stars" missions (type-2 / sub_type 1021) and
    keep their progress in sync with the recorded chapter state.

    These tasks ARE the official one-time 3-Star Reward for every stage. Rows
    are created at 0/1 with submit_time=0 so the player claims the reward from
    the Missions (branch) screen; a stage whose stars were already earned gets
    its row seeded claimable (progress = target)."""
    star_ids = _get_star_task_ids()
    if not star_ids:
        return

    existing = fetch_existing_task_ids(commander_id, star_ids)

    state = _chapter_progress_state(commander_id)
    now = int(__import__("time").time())
    fill_ids = []
    to_insert = []
    for tid in star_ids:
        template = _load_task_template(tid)
        if template is None:
            continue
        target_num = int(template.get("target_num", 1) or 1)
        target_chapter = _coerce_int(template.get("target_id", 0), 0)
        # Claimable when the stars are recorded by the battle path OR the
        # persisted counters already satisfy every star objective (stages
        # 3-starred before the tracking columns existed -- no later battle
        # would re-flag them, but the mission must still complete).
        fill = 0
        if target_chapter > 0:
            _info = state.get(target_chapter)
            if _info is not None and (
                _info["star"] == 1
                or _counters_satisfy_stars(_info["counts"], _chapter_star_template(target_chapter))
            ):
                fill = target_num
        if tid in existing:
            if fill > 0:
                fill_ids.append(tid)
            continue
        to_insert.append((commander_id, tid, fill, now))
    if to_insert:
        store.executemany(
            "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
            "VALUES ($1, $2, $3, $4, 0) ON CONFLICT DO NOTHING",
            to_insert,
        )
    if fill_ids:
        store.execute(
            "UPDATE commander_tasks SET progress = $3 "
            "WHERE commander_id = $1 AND task_id = ANY($2) AND submit_time = 0 AND progress < $3",
            commander_id, fill_ids, 1,
        )


_SHIPYARD_OPEN_META_CACHE: Optional[list] = None
_SHIPYARD_STATS_TYPE_CACHE: Optional[dict] = None


def _shipyard_stats_type_map() -> dict:
    """template_id -> ship_data_statistics 'type', cached process-wide."""
    global _SHIPYARD_STATS_TYPE_CACHE
    if _SHIPYARD_STATS_TYPE_CACHE is not None:
        return _SHIPYARD_STATS_TYPE_CACHE
    mapping: dict = {}
    try:
        try:
            import orjson
            _loads = orjson.loads
        except ImportError:
            _loads = json.loads
        from src.db.session import get_sync_session
        from sqlalchemy import text
        with get_sync_session() as session:
            rows = session.execute(
                text("SELECT key, data FROM config_entries WHERE category = :cat"),
                {"cat": "sharecfgdata/ship_data_statistics.json"},
            ).fetchall()
        for k, raw in rows:
            d = raw if isinstance(raw, dict) else _loads(raw)
            if not isinstance(d, dict):
                continue
            tid = d.get("id")
            ty = d.get("type")
            if tid is not None and ty is not None:
                try:
                    mapping[int(tid)] = int(ty)
                except (TypeError, ValueError):
                    continue
    except Exception:
        pass
    _SHIPYARD_STATS_TYPE_CACHE = mapping
    return mapping


def _shipyard_open_task_meta() -> list:
    """Metadata for every Dev Dock blueprint open-condition task.

    Each entry: {task_id, sub_type, target_num, nats/tys (sub_type 1040
    counting sets)}. Open-condition tasks must exist in commander_tasks so the
    client's ShipBluePrintScene can render the locked ship's prerequisite bars;
    a missing task VO makes updateInfo() index nil and the UI hard-crashes."""
    global _SHIPYARD_OPEN_META_CACHE
    if _SHIPYARD_OPEN_META_CACHE is not None:
        return _SHIPYARD_OPEN_META_CACHE
    metas: list = []
    all_tpl = _all_task_templates()
    try:
        entries = list_config_entries_sync("ShareCfg/ship_data_blueprint.json")
    except Exception:
        entries = []
    seen = set()
    for e in entries:
        d = e.data if isinstance(e.data, dict) else None
        if d is None:
            continue
        for raw in d.get("unlock_task_open_condition", []) or []:
            try:
                tid = int(raw)
            except (TypeError, ValueError):
                continue
            if tid in seen:
                continue
            seen.add(tid)
            tpl = all_tpl.get(tid)
            if not isinstance(tpl, dict):
                continue
            try:
                sub_type = int(tpl.get("sub_type", 0) or 0)
                target = int(tpl.get("target_num", 0) or 0)
            except (TypeError, ValueError):
                continue
            meta = {"task_id": tid, "sub_type": sub_type, "target": target,
                    "nats": set(), "tys": set(), "nation": None}
            if sub_type == 1040:
                pairs = tpl.get("target_id")
                if isinstance(pairs, list):
                    for p in pairs:
                        if isinstance(p, list) and len(p) >= 2:
                            try:
                                meta["nats"].add(int(p[0]))
                                meta["tys"].add(int(p[1]))
                            except (TypeError, ValueError):
                                pass
            elif sub_type == 1050:
                # faction tech points: target_id is the nation (str or int)
                try:
                    meta["nation"] = int(str(tpl.get("target_id", 0) or 0))
                except (TypeError, ValueError):
                    meta["nation"] = None
            metas.append(meta)
    _SHIPYARD_OPEN_META_CACHE = metas
    return metas


def _ensure_shipyard_open_tasks(store, commander_id: int):
    """Insert the Dev Dock open-condition tasks the client renders on locked
    blueprint cards (ShipBluePrintScene.updateInfo). Progress is counted from
    owned ships for the PR1-style collection conditions (sub_type 1040) and from
    the server-computed faction tech points for the PR2+/DR conditions
    (sub_type 1050); existing unsubmitted 1050 rows are refreshed on every
    login so they track the dock."""
    metas = _shipyard_open_task_meta()
    if not metas:
        return
    try:
        rows = store.fetch(
            "SELECT task_id, progress, submit_time FROM commander_tasks WHERE commander_id = $1",
            commander_id,
        )
        existing = {}
        for r in rows:
            try:
                existing[int(r[0])] = (int(r[1] or 0), int(r[2] or 0))
            except (TypeError, ValueError):
                continue
    except Exception:
        existing = {}
    missing = [m for m in metas if m["task_id"] not in existing]
    owned = set()
    types = _shipyard_stats_type_map()
    now = int(time.time())

    faction_points: Optional[dict] = None

    def _faction_points() -> dict:
        nonlocal faction_points
        if faction_points is None:
            from src.answer.shipyard_blueprint_helpers import compute_faction_tech_points
            faction_points = compute_faction_tech_points(commander_id, store) or {}
        return faction_points

    for m in missing:
        prog = 0
        if m["sub_type"] == 1040:
            if not owned:
                try:
                    srows = store.fetch(
                        "SELECT DISTINCT ship_id FROM owned_ships "
                        "WHERE owner_id = $1 AND deleted_at IS NULL",
                        commander_id,
                    )
                    owned = {int(r[0]) for r in srows}
                except Exception:
                    owned = set()
            try:
                cnt = sum(1 for tid in owned
                          if tid in types and int(str(tid)[0]) in m["nats"] and types[tid] in m["tys"])
                prog = min(cnt, m["target"])
            except Exception:
                prog = 0
        elif m["sub_type"] == 1050 and m.get("nation") is not None:
            prog = min(int(_faction_points().get(m["nation"], 0) or 0), m["target"])
        try:
            store.execute(
                "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
                "VALUES ($1, $2, $3, $4, 0) "
                "ON CONFLICT (commander_id, task_id) DO NOTHING",
                commander_id, m["task_id"], prog, now,
            )
        except Exception:
            pass

    # Refresh faction-tech (1050) progress for already-existing unsubmitted
    # rows whose value drifted (the client derives the displayed bar itself, but
    # SC_20001 rows must stay honest -- they used to sit at 0 forever).
    for m in metas:
        if m["sub_type"] != 1050 or m.get("nation") is None:
            continue
        prev = existing.get(m["task_id"])
        if prev is None or prev[1] != 0:
            continue
        prog = min(int(_faction_points().get(m["nation"], 0) or 0), m["target"])
        if prev[0] == prog:
            continue
        try:
            store.execute(
                "UPDATE commander_tasks SET progress = $1 "
                "WHERE commander_id = $2 AND task_id = $3 AND submit_time = 0",
                prog, commander_id, m["task_id"],
            )
        except Exception:
            pass


def _region_day_start(now_ts: int) -> int:
    """Region-local start-of-day timestamp, aligned to the client's
    IsSameDay anchor (monday_0oclock_timestamp, region-local midnight)."""
    return daily_window(datetime.fromtimestamp(now_ts, tz=timezone.utc)).key


def _today_utc_start() -> int:
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    return int(datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc).timestamp())


def _ensure_daily_tasks(store, commander_id: int):
    daily_ids = _get_daily_task_ids()
    if not daily_ids:
        return

    now = int(time.time())
    day_start = _region_day_start(now)
    existing = {}
    rows = store.fetch(
        "SELECT task_id, submit_time, accept_time FROM commander_tasks WHERE commander_id = $1 AND task_id = ANY($2)",
        commander_id, daily_ids,
    )
    for r in rows:
        existing[r[0]] = (r[1], r[2])

    for tid in daily_ids:
        if tid in existing:
            submit_time, accept_time = existing[tid]
            # Reset EVERY daily task that belongs to a previous region-local day.
            # A task accepted before the current day's boundary is stale and must
            # be wiped (progress + claim), regardless of claim/completion state.
            if accept_time is None or accept_time < day_start:
                store.execute(
                    "UPDATE commander_tasks SET submit_time = 0, progress = 0, accept_time = $1 "
                    "WHERE commander_id = $2 AND task_id = $3",
                    now, commander_id, tid,
                )
        else:
            store.execute(
                "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
                "VALUES ($1, $2, 0, $3, 0) ON CONFLICT DO NOTHING",
                commander_id, tid, now,
            )


def _task_first_daily_pre_id() -> int:
    """Client gate: TaskScene.IsPassScenario() returns
    task_first_daily_pre_id < smallest ACTIVE type-1 task id. The pre-daily
    (tutorial) main missions with id <= this value must be claimed
    (submit_time > 0) for a progressed commander, else the client hides the
    Weekly tab (TaskWeekPage.Update -> setActive(_tf, false))."""
    try:
        entry = get_config_entry_sync("ShareCfg/gameset.json", "task_first_daily_pre_id")
        if entry is not None:
            data = entry.data
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, dict):
                v = data.get("key_value")
                if v:
                    return int(v)
    except Exception:
        pass
    return 4


def _commander_is_progressed(store, commander_id: int) -> bool:
    """Any owned ship with level >= 2 means the commander is past onboarding
    (fresh accounts only have level-1 starter ships)."""
    try:
        row = store.fetchrow(
            "SELECT count(*) FROM owned_ships WHERE owner_id = $1 AND level > 1 AND deleted_at IS NULL",
            commander_id,
        )
        if row is not None and row[0] > 0:
            return True
    except Exception:
        pass
    return False


def _ensure_main_tasks(store, commander_id: int):
    main_ids = _get_main_task_ids()
    if not main_ids:
        return

    existing = fetch_existing_task_ids(commander_id, main_ids)

    now = int(__import__("time").time())
    pre_id = _task_first_daily_pre_id()
    progressed = _commander_is_progressed(store, commander_id)
    to_insert_pre = []
    to_insert_norm = []
    update_pre = []
    for tid in main_ids:
        template = _load_task_template(tid)
        target_num = template.get("target_num", 1) if template else 1
        is_pre_daily = progressed and tid <= pre_id
        if tid in existing:
            if is_pre_daily:
                update_pre.append((target_num, now, commander_id, tid))
            continue
        if is_pre_daily:
            to_insert_pre.append((commander_id, tid, target_num, now, now))
        else:
            to_insert_norm.append((commander_id, tid, now))

    if update_pre:
        store.executemany(
            "UPDATE commander_tasks SET progress = $1, submit_time = $2 "
            "WHERE commander_id = $3 AND task_id = $4 AND submit_time = 0",
            update_pre,
        )
    if to_insert_pre:
        store.executemany(
            "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            to_insert_pre,
        )
    if to_insert_norm:
        store.executemany(
            "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
            "VALUES ($1, $2, 0, $3, 0) ON CONFLICT (commander_id, task_id) DO NOTHING",
            to_insert_norm,
        )

    # Official one-time first-clear rewards are the scenario "Clear X-Y" tasks
    # (type-1, sub_type 1020, ids 4-67; target = chapter id). A stage cleared
    # before this row was seeded (or before the per-battle emit ran) must still
    # become claimable -- refresh unsubmitted rows whose chapter is already
    # cleared (pass_count >= 1).
    fill_ids = []
    for tid in main_ids:
        template = _load_task_template(tid)
        if template is None:
            continue
        if int(template.get("sub_type", 0) or 0) != 1020:
            continue
        target_chapter = _coerce_int(template.get("target_id", 0), 0)
        if target_chapter > 0 and _chapter_cleared(commander_id, target_chapter):
            fill_ids.append(tid)
    if fill_ids:
        store.execute(
            "UPDATE commander_tasks SET progress = $3 "
            "WHERE commander_id = $1 AND task_id = ANY($2) AND submit_time = 0 AND progress < $3",
            commander_id, fill_ids, 1,
        )


def _push_progress_update(client: Client, task_ids: list):
    if not task_ids:
        return
    from src.protobuf import protobuf
    store = get_default_store()
    if store is None:
        return
    try:
        # Manual sub-tasks of locked Handbook pages keep progressing in the DB
        # but are invisible to the client (no VO) until their page unlocks.
        from src.answer.commandermisc.handlers import _locked_manual_subtask_ids
        locked = _locked_manual_subtask_ids(client, store, client.commander.commander_id)
        if locked:
            task_ids = [t for t in task_ids if t not in locked]
    except Exception:
        pass
    if not task_ids:
        return
    try:
        rows = fetch_commander_tasks(client.commander.commander_id, task_ids)
    except Exception:
        return
    response = protobuf.SC_20002()
    for r in rows:
        response.info.append(protobuf.TASK_PROGRESS(id=r.task_id, progress=r.progress))
    _send_message(client, 20002, response)


def handle_commander_missions(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    store = get_default_store()
    from src.protobuf import protobuf

    if store is not None:
        try:
            import time as _time
            _t0 = _time.monotonic()
            _ensure_main_tasks(store, client.commander.commander_id)
            # Official "Get 3 stars in stage X-Y" missions (type-2, sub_type
            # 1021) -- the real one-time 3-Star Reward for each stage.
            _ensure_star_tasks(store, client.commander.commander_id)
            _ensure_daily_tasks(store, client.commander.commander_id)
            _t1 = _time.monotonic()
            from src.answer.commandermisc.handlers import _ensure_manual_tasks
            _ensure_manual_tasks(client, store, client.commander.commander_id, int(time.time()), push_add=False)
            _t2 = _time.monotonic()
            from src.answer.commandermisc.handlers import _ensure_tech_tasks
            _ensure_tech_tasks(client, store, client.commander.commander_id, int(time.time()), push_add=False)
            # Possession/state-based tasks ("Possess N Level-X ships", "own 3
            # Elite+ gear", "join a guild", "reach N tech points", ...): the
            # client renders them from its own data mirrors, but the server
            # progress rows must match or Handbook pages stall. Recomputed
            # AFTER the seed so the freshly inserted rows get their real values.
            if client is not None and not getattr(client, "_possession_synced", False):
                try:
                    _sync_possession_tasks_sync(client)
                    client._possession_synced = True
                except Exception:
                    pass
            # Dev Dock (ShipBluePrint) open-condition tasks -- without them the
            # client crashes rendering locked blueprint cards.
            _ensure_shipyard_open_tasks(store, client.commander.commander_id)
            _t3 = _time.monotonic()
            rows = fetch_all_commander_tasks(client.commander.commander_id)

            from src.answer.commandermisc.handlers import _tech_task_ids, _manual_config
            tech_set = set(_tech_task_ids())
            # Manual (Commander Handbook) sub-tasks: Rookie (220xx) + Guide (230xx).
            # These are what the Handbook pages render, so they must survive the
            # client's SC_20001 stream truncation. Emit them FIRST.
            try:
                manual_set = set(_manual_config()["subtasks"])
            except Exception:
                manual_set = set()
            manual_rows = [r for r in rows if r[0] in manual_set]
            # Handbook sub-tasks of LOCKED pages are tracked in the DB but must
            # not reach the client: TaskProxy VOs with claimable progress badge
            # the locked tab (ShouldShowTip) while the tab cannot be opened to
            # claim. When the page unlocks the tasks go out via CS_22302 +
            # TASK_ADD with the accumulated progress.
            try:
                from src.answer.commandermisc.handlers import _locked_manual_subtask_ids
                locked_ids = _locked_manual_subtask_ids(client, store, client.commander.commander_id)
                if locked_ids:
                    manual_rows = [r for r in manual_rows if r[0] not in locked_ids]
            except Exception:
                pass
            tech_rows = [r for r in rows if r[0] in tech_set and r[0] not in manual_set]
            other_rows = [r for r in rows if r[0] not in manual_set and r[0] not in tech_set]

            # The client caps the TOTAL SC_20001 task stream (byte/row budget for
            # the whole commander_tasks sync) and silently drops the high-id tail.
            # On a large account the Handbook tasks (Rookie/Guide, ids ~22000-23109)
            # and the Fresh Tech Catchup tasks (51101-51240) would land in the
            # dropped region and fall back to a fake "Completed" state. Emit the
            # manual + tech tasks FIRST so they sit at the front of the stream and
            # survive the truncation. initTaskInfo accumulates across packets (it
            # never clears data), so ordering within the stream is irrelevant.
            def _send_batch(batch):
                if not batch:
                    return
                resp = protobuf.SC_20001()
                for r in batch:
                    resp.info.append(protobuf.TASKINFO(
                        id=r[0], progress=r[1], accept_time=r[2], submit_time=r[3]))
                d = resp.SerializeToString()
                h = generate_packet_header(20001, d, client.packet_index)
                client.write_to_buffer(h + d)

            BATCH = 400
            for i in range(0, len(manual_rows), BATCH):
                _send_batch(manual_rows[i:i + BATCH])
            for i in range(0, len(tech_rows), BATCH):
                _send_batch(tech_rows[i:i + BATCH])
            for i in range(0, len(other_rows), BATCH):
                _send_batch(other_rows[i:i + BATCH])
            _t4 = _time.monotonic()
            log_event("Tasks", "SC_20001Sync",
                      f"cmd={client.commander.commander_id} rows={len(rows)} "
                      f"main+daily={(_t1 - _t0) * 1000:.0f}ms manual={(_t2 - _t1) * 1000:.0f}ms "
                      f"tech={(_t3 - _t2) * 1000:.0f}ms fetch+send={(_t4 - _t3) * 1000:.0f}ms",
                      LOG_LEVEL_WARN if (_t4 - _t0) >= 1.0 else LOG_LEVEL_DEBUG)
        except Exception as e:
            pass

    return 0, 20001, None


async def handle_weekly_missions(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.answer.weekly_task_cluster import handle_weekly_missions as _weekly
    result = await _weekly(buffer, client)
    return result


def handle_submit_task(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    try:
        payload = protobuf.CS_20005()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 20006, e

    template = _load_task_template(payload.id)
    if template is None:
        return _send_message(client, 20006, protobuf.SC_20006(result=RESULT_FAILED))

    drops, ok = _submit_task_and_get_drops(client, payload.id, template, 0)
    if not ok:
        return _send_message(client, 20006, protobuf.SC_20006(result=RESULT_FAILED))

    _maybe_accept_mingshi_next_task(client, payload.id)

    response = protobuf.SC_20006(result=RESULT_SUCCESS)
    response.award_list.extend(_drop_map_to_sorted_list(drops))
    return _send_message(client, 20006, response)


def handle_accept_task(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    try:
        payload = protobuf.CS_20007()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 20008, e

    template = _load_task_template(payload.id)
    if template is None:
        return _send_message(client, 20008, protobuf.SC_20008(result=RESULT_FAILED))

    store = get_default_store()
    if store is None:
        return 0, 20008, Exception("store not available")

    commander_id = client.commander.commander_id
    now = int(__import__("time").time())

    try:
        create_or_accept_task(commander_id, payload.id, now)
    except Exception as e:
        return 0, 20008, e

    ti = protobuf.TASK_ADD(id=payload.id, progress=0, accept_time=now, submit_time=0)
    return _send_message(client, 20008, protobuf.SC_20008(result=RESULT_SUCCESS, task=ti))


TASK_PROGRESS_UPDATE = 0
TASK_PROGRESS_APPEND = 1

def handle_update_task_progress(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    try:
        payload = protobuf.CS_20009()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 20010, e

    updates = payload.progressinfo
    if len(updates) == 0:
        return _send_message(client, 20010, protobuf.SC_20010(result=RESULT_FAILED))

    store = get_default_store()
    if store is None:
        return 0, 20010, Exception("store not available")

    commander_id = client.commander.commander_id
    now = int(__import__("time").time())

    for update in updates:
        template = _load_task_template(update.id)
        if template is None:
            continue
        target_num = template.get("target_num", 0)
        mode = getattr(update, "mode", TASK_PROGRESS_UPDATE)
        progress = update.progress
        try:
            store.execute(
                "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
                "VALUES ($1, $2, CASE WHEN $5 > 0 THEN LEAST($4, $5) ELSE $4 END, $6, 0) "
                "ON CONFLICT (commander_id, task_id) DO UPDATE SET progress = CASE "
                "  WHEN $3 = 0 THEN CASE WHEN $5 > 0 THEN LEAST($4, $5) ELSE $4 END "
                "  ELSE CASE WHEN $5 > 0 THEN LEAST(commander_tasks.progress + $4, $5) ELSE commander_tasks.progress + $4 END "
                "END",
                commander_id, update.id, mode, progress, target_num, now,
            )
        except Exception as e:
            return 0, 20010, e

    _push_progress_update(client, [update.id for update in updates])
    return _send_message(client, 20010, protobuf.SC_20010(result=RESULT_SUCCESS))


def handle_submit_task_batch(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    try:
        payload = protobuf.CS_20011()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 20012, e

    response = protobuf.SC_20012(id_list=[], award_list=[])
    seen = set()
    merged = {}

    for task_id in payload.id_list:
        if task_id in seen:
            continue
        seen.add(task_id)

        template = _load_task_template(task_id)
        if template is None:
            continue

        drops, ok = _submit_task_and_get_drops(client, task_id, template, 0)
        if not ok:
            continue

        _maybe_accept_mingshi_next_task(client, task_id)

        response.id_list.append(task_id)
        for drop in drops.values():
            _accumulate_drop(merged, drop["type"], drop["id"], drop["number"])

    response.award_list.extend(_drop_map_to_sorted_list(merged))
    return _send_message(client, 20012, response)


def handle_submit_quick_task(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    try:
        payload = protobuf.CS_20013()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 20014, e

    template = _load_task_template(payload.id)
    if template is None:
        return _send_message(client, 20014, protobuf.SC_20014(result=RESULT_FAILED))

    quick_finish = template.get("quick_finish", 0)
    if quick_finish == 0 or payload.item_cost != quick_finish:
        return _send_message(client, 20014, protobuf.SC_20014(result=RESULT_FAILED))

    drops, ok = _submit_task_and_get_drops(client, payload.id, template, quick_finish)
    if not ok:
        return _send_message(client, 20014, protobuf.SC_20014(result=RESULT_FAILED))

    response = protobuf.SC_20014(result=RESULT_SUCCESS)
    response.award_list.extend(_drop_map_to_sorted_list(drops))
    return _send_message(client, 20014, response)


def _coerce_int(v, default=0):
    if isinstance(v, list):
        for x in v:
            r = _coerce_int(x, None)
            if r is not None:
                return r
        return default
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


_task_event_cache = None
def _build_task_event_cache():
    global _task_event_cache
    from src.orm.config_entry import list_config_entries_sync
    entries = list_config_entries_sync("sharecfgdata/task_data_template.json")
    cache = {}
    for e in entries:
        try:
            data = e.data if isinstance(e.data, dict) else __import__("json").loads(e.data)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        tid = data.get("id")
        st = data.get("sub_type")
        tg = data.get("target_id", 0)
        if tid and st is not None:
            try:
                st = int(st)
            except (TypeError, ValueError):
                continue
            targets = []
            if isinstance(tg, (list, tuple)):
                for x in tg:
                    try:
                        n = int(x)
                        if n > 0:
                            targets.append(n)
                    except (TypeError, ValueError):
                        pass
                if not targets:
                    targets = [0]
            elif isinstance(tg, dict):
                targets = [0]
            else:
                try:
                    targets = [int(tg)]
                except (TypeError, ValueError):
                    targets = [0]

            for t in set(targets):
                cache.setdefault((st, t), []).append(int(tid))
    _task_event_cache = cache

def handle_task_progress_event(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    try:
        payload = protobuf.CS_20016()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 20017, e

    event_type = payload.event_type
    event_target = payload.event_target
    event_count = payload.event_count
    if event_type == 0 or event_count == 0:
        return _send_message(client, 20017, protobuf.SC_20017(result=RESULT_FAILED))

    schedule_emit(client, event_type, event_target, event_count)
    return _send_message(client, 20017, protobuf.SC_20017(result=RESULT_SUCCESS))


async def _emit_task_progress(client: Client, event_type: int, event_target: int, event_count: int):
    """Server-authoritative task progress. Matches tasks by (sub_type, target_id)
    and (sub_type, 0); increments their progress (capped at target_num) and pushes
    SC_20002 so the client displays it. Called on game events (battle win, build, …)
    and from handle_task_progress_event (CS_20016). Async so it never blocks the
    response path (the per-event DB write is offloaded to the event loop)."""
    if event_type == 0 or event_count == 0:
        return

    global _task_event_cache
    if _task_event_cache is None:
        _build_task_event_cache()

    matched = list(_task_event_cache.get((event_type, event_target), []))
    matched += _task_event_cache.get((event_type, 0), [])
    task_ids = []
    seen = set()
    for tid in matched:
        if tid not in seen:
            seen.add(tid)
            task_ids.append(tid)
    if not task_ids:
        return

    store = get_default_store()
    if store is None:
        return

    commander_id = client.commander.commander_id
    now = int(time.time())

    for tid in task_ids:
        # Dev Dock chain missions (sub_type 110 Theoretical Research, 1041
        # Combat Data Collection, 1000 Design Breakthrough, ...) only accrue
        # while that development is running, the stage's 24h unlock offset
        # passed AND every open_need predecessor is submitted (the generic
        # event would otherwise pre-fill locked / not-started chain rows).
        try:
            from src.answer.shipyard_blueprint_helpers import is_dev_chain_task_open
            if is_dev_chain_task_open(commander_id, tid, now) is False:
                continue
        except Exception:
            pass
        template = _load_task_template(tid)
        if template is None:
            continue
        target_num = template.get("target_num", 0)
        if target_num <= 0:
            continue
        try:
            task_type = int(template.get("type", 0) or 0)
        except (TypeError, ValueError):
            task_type = 0
        try:
            if task_type not in SERVER_TRACKED_TASK_TYPES:
                # UPDATE-only. Server-managed types (main/branch/daily/weekly) are
                # tracked without an explicit accept; event-family tasks (type 5/6/
                # 26/36/..., the old events' Side/Daily missions) must exist ONLY
                # after their event granted them -- creating rows here used to
                # materialize every old event's task list on the first battle.
                await asyncio.to_thread(
                    store.execute,
                    "UPDATE commander_tasks SET progress = LEAST(progress + $3, $4) "
                    "WHERE commander_id = $1 AND task_id = $2 AND submit_time = 0",
                    commander_id, tid, event_count, target_num,
                )
            else:
                await asyncio.to_thread(
                    upsert_task_progress_least,
                    commander_id, tid, event_count, target_num, now,
                )
        except Exception:
            pass

    _push_progress_update(client, task_ids)
    await _emit_weekly_progress(client, event_type, event_target, event_count)


_WEEKLY_EVENT_CACHE = None
_WEEKLY_LOCKS: dict = {}
_WEEKLY_TEMPLATE_CACHE: dict = {}
_WEEKLY_CHAINS_CACHE: Optional[dict] = None


def _get_weekly_chains() -> dict:
    global _WEEKLY_CHAINS_CACHE, _WEEKLY_TEMPLATE_CACHE
    if _WEEKLY_CHAINS_CACHE is not None:
        return _WEEKLY_CHAINS_CACHE
    from src.orm.config_entry import list_config_entries_sync
    entries = list_config_entries_sync("ShareCfg/weekly_task_template.json")
    chains = {}
    for e in entries:
        try:
            data = e.data if isinstance(e.data, dict) else json.loads(e.data)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        tid = data.get("id")
        st = data.get("sub_type")
        if tid is None or st is None:
            continue
        try:
            tid = int(tid)
            st = int(st)
        except (TypeError, ValueError):
            continue
        _WEEKLY_TEMPLATE_CACHE[tid] = data
        chains.setdefault(st, []).append(data)
    for st in chains:
        chains[st].sort(key=lambda t: (t.get("target_num", 0), t.get("id", 0)))
    _WEEKLY_CHAINS_CACHE = chains
    return chains


def _build_weekly_event_cache():
    global _WEEKLY_EVENT_CACHE
    chains = _get_weekly_chains()
    cache = {}
    for st, tasks in chains.items():
        for data in tasks:
            tid = data.get("id")
            tg = _coerce_int(data.get("target_id", 0), 0)
            if tid is not None:
                cache.setdefault((st, tg), []).append(int(tid))
    _WEEKLY_EVENT_CACHE = cache


def _load_weekly_template(task_id: int):
    if not task_id:
        return None
    tid = int(task_id)
    if tid in _WEEKLY_TEMPLATE_CACHE:
        return _WEEKLY_TEMPLATE_CACHE[tid]
    _get_weekly_chains()
    if tid in _WEEKLY_TEMPLATE_CACHE:
        return _WEEKLY_TEMPLATE_CACHE[tid]
    entry = get_config_entry_sync("ShareCfg/weekly_task_template.json", str(tid))
    if entry is None:
        return None
    data = entry.data
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            _WEEKLY_TEMPLATE_CACHE[tid] = parsed
            return parsed
        except Exception:
            return None
    _WEEKLY_TEMPLATE_CACHE[tid] = data
    return data


def _sync_load_weekly_state(commander_id: int):
    return load_weekly_state(commander_id)


def _sync_save_weekly_state(commander_id: int, state: dict, week_bucket: int):
    save_weekly_state(commander_id, state, week_bucket)


def _sync_init_weekly_state(commander_id: int) -> bool:
    """Build the initial weekly task set (one active sub-task per sub_type,
    the lowest target_num) and insert the row if it does not exist."""
    from src.orm.config_entry import list_config_entries_sync
    entries = list_config_entries_sync("ShareCfg/weekly_task_template.json")
    by_sub = {}
    for e in entries:
        try:
            data = e.data if isinstance(e.data, dict) else json.loads(e.data)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        sub = data.get("sub_type")
        if sub is None:
            continue
        try:
            sub = int(sub)
        except (TypeError, ValueError):
            continue
        cur = by_sub.get(sub)
        if cur is None or (data.get("target_num", 0), data.get("id", 0)) < (cur.get("target_num", 0), cur.get("id", 0)):
            by_sub[sub] = data
    tasks = [{"id": int(d["id"]), "progress": 0} for d in by_sub.values() if d.get("id")]
    if not tasks:
        return False
    week_bucket = _region_week_bucket_for(int(time.time()))
    _sync_save_weekly_state(commander_id, {"tasks": tasks, "counts": {}, "pt": 0, "reward_lv": 0}, week_bucket)
    return True


async def _async_load_weekly_state(commander_id: int):
    return await aload_weekly_state(commander_id)


async def _async_save_weekly_state(commander_id: int, state: dict, week_bucket: int):
    await asave_weekly_state(commander_id, state, week_bucket)


async def _async_init_weekly_state(commander_id: int) -> bool:
    """Async variant of _sync_init_weekly_state (one active sub-task per sub_type,
    the lowest target_num). Used by the async emit path."""
    from src.orm.config_entry import list_config_entries_sync
    entries = list_config_entries_sync("ShareCfg/weekly_task_template.json")
    by_sub = {}
    for e in entries:
        try:
            data = e.data if isinstance(e.data, dict) else json.loads(e.data)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        sub = data.get("sub_type")
        if sub is None:
            continue
        try:
            sub = int(sub)
        except (TypeError, ValueError):
            continue
        cur = by_sub.get(sub)
        if cur is None or (data.get("target_num", 0), data.get("id", 0)) < (cur.get("target_num", 0), cur.get("id", 0)):
            by_sub[sub] = data
    tasks = [{"id": int(d["id"]), "progress": 0} for d in by_sub.values() if d.get("id")]
    if not tasks:
        return False
    week_bucket = _region_week_bucket_for(int(time.time()))
    await _async_save_weekly_state(commander_id, {"tasks": tasks, "counts": {}, "pt": 0, "reward_lv": 0}, week_bucket)
    return True


async def _emit_weekly_progress(client: Client, event_type: int, event_target: int, event_count: int):
    """Weekly sub-tasks share the same (sub_type, target_id) event space as daily
    tasks. Advance the CURRENTLY-ACTIVE weekly sub-task(s) for the matched event
    type, capped at target_num, and push SC_20102 so the client shows progress."""
    global _WEEKLY_EVENT_CACHE, _WEEKLY_LOCKS
    if _WEEKLY_EVENT_CACHE is None:
        _build_weekly_event_cache()
    if not _WEEKLY_EVENT_CACHE:
        return

    matched = list(_WEEKLY_EVENT_CACHE.get((event_type, event_target), []))
    matched += _WEEKLY_EVENT_CACHE.get((event_type, 0), [])
    seen = set()
    dedup = []
    for tid in matched:
        if tid not in seen:
            seen.add(tid)
            dedup.append(tid)
    matched = dedup
    if not matched:
        return

    commander_id = client.commander.commander_id
    # Serialize all weekly-state mutations for a commander so concurrent battle
    # emits (1020/20/11/23) can't load-modify-save the same row and lose updates.
    # Key by (commander_id, loop) so separate event loops (e.g. per-test
    # asyncio.run) don't reuse a lock bound to a dead loop.
    loop = asyncio.get_running_loop()
    lock = _WEEKLY_LOCKS.get((commander_id, id(loop)))
    if lock is None:
        _WEEKLY_LOCKS[(commander_id, id(loop))] = lock = asyncio.Lock()
    async with lock:
        state = await _async_load_weekly_state(commander_id)
        if state is None or not state["tasks"]:
            # Weekly progress should accumulate even before the player first opens
            # the Weekly tab (which is what lazily creates the row). Initialize it
            # on demand so game events are not lost.
            if not await _async_init_weekly_state(commander_id):
                return
            state = await _async_load_weekly_state(commander_id)
            if state is None or not state["tasks"]:
                return

        active_ids = {t.get("id") for t in state["tasks"]}
        counts = state.get("counts", {})
        updated = set()
        for tid in matched:
            if tid not in active_ids:
                continue
            tmpl = _load_weekly_template(tid)
            if tmpl is None:
                continue
            target_num = tmpl.get("target_num", 0)
            if target_num <= 0:
                continue
            sub_type = _coerce_int(tmpl.get("sub_type"), 0)
            key = str(sub_type)
            counts[key] = int(counts.get(key, 0)) + event_count
            for t in state["tasks"]:
                if t.get("id") == tid:
                    t["progress"] = min(int(counts[key]), target_num)
                    updated.add(tid)
                    break
        if not updated:
            return

        state["counts"] = counts
        week_bucket = _region_week_bucket_for(int(time.time()))
        await _async_save_weekly_state(commander_id, state, week_bucket)
    _push_weekly_progress_update(client, updated, state)


def _push_weekly_progress_update(client: Client, ids: set, state: dict):
    from src.protobuf import protobuf
    response = protobuf.SC_20102()
    for t in state["tasks"]:
        if t.get("id") in ids:
            response.task.append(protobuf.WEEKLY_TASK_P20(id=t["id"], progress=int(t.get("progress", 0))))
    _send_message(client, 20102, response)


def _weekly_targets():
    entry = get_config_entry_sync("ShareCfg/gameset.json", "weekly_target")
    if entry is None:
        return None
    data = entry.data
    if isinstance(data, str):
        data = json.loads(data)
    desc = data.get("description") if isinstance(data, dict) else data
    if isinstance(desc, str):
        try:
            desc = json.loads(desc)
        except Exception:
            return None
    return desc


def _weekly_drops():
    entry = get_config_entry_sync("ShareCfg/gameset.json", "weekly_drop_client")
    if entry is None:
        return None
    data = entry.data
    if isinstance(data, str):
        data = json.loads(data)
    desc = data.get("description") if isinstance(data, dict) else data
    if isinstance(desc, str):
        try:
            desc = json.loads(desc)
        except Exception:
            return None
    return desc


def _find_next_weekly_task(sub_type, current_id):
    chains = _get_weekly_chains()
    try:
        sub_type = int(sub_type)
    except (TypeError, ValueError):
        return None
    same = chains.get(sub_type, [])
    for i, t in enumerate(same):
        if t.get("id") == current_id and i + 1 < len(same):
            return same[i + 1].get("id")
    return None


def _send_weekly_pt(client: Client, pt: int):
    from src.protobuf import protobuf
    _send_message(client, 20105, protobuf.SC_20105(pt=pt))


def handle_submit_weekly_task(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    try:
        payload = protobuf.CS_20106()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 20107, e

    commander_id = client.commander.commander_id
    tid = payload.id
    state = _sync_load_weekly_state(commander_id)
    if state is None:
        return _send_message(client, 20107, protobuf.SC_20107(result=RESULT_FAILED))

    task = None
    for t in state["tasks"]:
        if t.get("id") == tid:
            task = t
            break
    if task is None:
        return _send_message(client, 20107, protobuf.SC_20107(result=RESULT_FAILED))

    tmpl = _load_weekly_template(tid)
    if tmpl is None:
        return _send_message(client, 20107, protobuf.SC_20107(result=RESULT_FAILED))

    target_num = tmpl.get("target_num", 0)
    if int(task.get("progress", 0)) < target_num:
        return _send_message(client, 20107, protobuf.SC_20107(result=RESULT_FAILED))

    award = tmpl.get("award_display")
    pt_gain = 0
    if isinstance(award, list) and len(award) >= 3:
        pt_gain = int(award[2])
    state["pt"] = state["pt"] + pt_gain

    sub_type = _coerce_int(tmpl.get("sub_type"), 0)
    counts = state.get("counts", {})
    key = str(sub_type)
    cur_count = int(counts.get(key, 0))

    next_id = _find_next_weekly_task(tmpl.get("sub_type"), tid)
    next_template = _load_weekly_template(next_id) if next_id else None
    next_target = next_template.get("target_num", 0) if next_template else 0
    next_progress = min(cur_count, next_target) if next_id else 0

    new_tasks = []
    for t in state["tasks"]:
        if t.get("id") == tid:
            if next_id:
                new_tasks.append({"id": next_id, "progress": next_progress})
        else:
            new_tasks.append(t)
    state["tasks"] = new_tasks
    state["counts"] = counts

    week_bucket = _region_week_bucket_for(int(time.time()))
    _sync_save_weekly_state(commander_id, state, week_bucket)

    next_proto = protobuf.WEEKLY_TASK_P20(id=next_id, progress=next_progress) if next_id else protobuf.WEEKLY_TASK_P20(id=0, progress=0)
    return _send_message(client, 20107, protobuf.SC_20107(result=RESULT_SUCCESS, next=next_proto))


def handle_submit_weekly_task_batch(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    """Weekly "Collect All" (CS_20108 -> SC_20109). Submits every finished weekly
    sub-task in the request, cascading through all consecutive completed stages in
    each chain, accumulating pt and returning the first uncompleted sub-task for each
    chain (or omitting it if the entire chain is finished)."""
    from src.protobuf import protobuf
    try:
        payload = protobuf.CS_20108()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 20109, e

    commander_id = client.commander.commander_id
    state = _sync_load_weekly_state(commander_id)
    if state is None:
        return _send_message(client, 20109, protobuf.SC_20109(result=RESULT_FAILED, pt=0))

    ids = [int(t) for t in payload.id]
    counts = state.get("counts", {})
    batch_pt = 0
    new_next = []
    advanced = False

    tasks_by_id = {t["id"]: t for t in state.get("tasks", []) if isinstance(t, dict) and "id" in t}
    replaced_tasks: dict[int, Optional[dict]] = {}

    for tid in ids:
        task = tasks_by_id.get(tid)
        if task is None:
            continue
        tmpl = _load_weekly_template(tid)
        if tmpl is None:
            continue
        sub_type = _coerce_int(tmpl.get("sub_type"), 0)
        target_num = tmpl.get("target_num", 0)
        cur_count = int(counts.get(str(sub_type), 0))
        task_prog = int(task.get("progress", 0))
        if task_prog > cur_count:
            cur_count = task_prog
            counts[str(sub_type)] = cur_count

        if cur_count < target_num and task_prog < target_num:
            continue

        cur_tid = tid
        cur_tmpl = tmpl
        chain_advanced = False

        while cur_tid is not None and cur_tmpl is not None:
            stage_target = cur_tmpl.get("target_num", 0)
            if stage_target <= 0:
                break
            if cur_count < stage_target:
                break

            award = cur_tmpl.get("award_display")
            if isinstance(award, list) and len(award) >= 3:
                batch_pt += int(award[2])
            chain_advanced = True

            stage_sub_type = _coerce_int(cur_tmpl.get("sub_type"), 0)
            next_id = _find_next_weekly_task(stage_sub_type, cur_tid)
            if not next_id:
                cur_tid = None
                cur_tmpl = None
                break

            cur_tid = next_id
            cur_tmpl = _load_weekly_template(next_id)

        if chain_advanced:
            advanced = True
            if cur_tid is not None and cur_tmpl is not None:
                next_target = cur_tmpl.get("target_num", 0)
                next_progress = min(cur_count, next_target)
                replaced_tasks[tid] = {"id": cur_tid, "progress": next_progress}
                new_next.append(protobuf.WEEKLY_TASK_P20(id=cur_tid, progress=next_progress))
            else:
                replaced_tasks[tid] = None

    if not advanced:
        return _send_message(client, 20109, protobuf.SC_20109(result=RESULT_FAILED, pt=0))

    new_tasks = []
    for t in state.get("tasks", []):
        t_id = t.get("id")
        if t_id in replaced_tasks:
            replacement = replaced_tasks[t_id]
            if replacement is not None:
                new_tasks.append(replacement)
        else:
            new_tasks.append(t)
    state["tasks"] = new_tasks

    state["pt"] = state.get("pt", 0) + batch_pt
    state["counts"] = counts
    week_bucket = _region_week_bucket_for(int(time.time()))
    _sync_save_weekly_state(commander_id, state, week_bucket)

    resp = protobuf.SC_20109(result=RESULT_SUCCESS, pt=batch_pt)
    resp.next.extend(new_next)
    return _send_message(client, 20109, resp)


def handle_submit_weekly_progress(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    try:
        payload = protobuf.CS_20110()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 20111, e

    commander_id = client.commander.commander_id
    state = _sync_load_weekly_state(commander_id)
    if state is None:
        return _send_message(client, 20111, protobuf.SC_20111(result=RESULT_FAILED))

    targets = _weekly_targets()
    drops = _weekly_drops()
    if not targets or not drops:
        return _send_message(client, 20111, protobuf.SC_20111(result=RESULT_FAILED))

    reward_lv = state["reward_lv"]
    # Client weektaskprogress.lua: index = table.indexof(targets, reward_lv) or 0
    # (1-based Lua index), then target = targets[index+1], drops = dropData[index+1].
    # In 0-based Python the client's `index` is `targets.index(reward_lv) + 1` when
    # reward_lv is present, else 0. The just-claimed tier becomes the new reward_lv.
    idx = targets.index(reward_lv) + 1 if reward_lv in targets else 0
    if idx >= len(targets):
        return _send_message(client, 20111, protobuf.SC_20111(result=RESULT_FAILED))
    target = targets[idx]
    if state["pt"] < target:
        return _send_message(client, 20111, protobuf.SC_20111(result=RESULT_FAILED))

    drop_idx = idx
    drop_list = drops[drop_idx]
    d = {}
    if isinstance(drop_list, list):
        for entry in drop_list:
            if len(entry) < 3:
                continue
            for (t, i, c) in _expand_award_entry(entry[0], entry[1], entry[2]):
                _accumulate_drop(d, t, i, c)

    _apply_drops(client, d)
    state["reward_lv"] = target
    week_bucket = _region_week_bucket_for(int(time.time()))
    _sync_save_weekly_state(commander_id, state, week_bucket)

    resp = protobuf.SC_20111(result=RESULT_SUCCESS)
    resp.award_list.extend(_drop_map_to_sorted_list(d))
    return _send_message(client, 20111, resp)


async def emit_task_progress(client: Client, event_type: int, event_target: int, event_count: int):
    """Public entry point for server game logic to advance tasks.

    Async: the per-event DB write is offloaded to the event loop so calling it
    via `schedule_emit(...)` never blocks the response path. Flushes at the end
    so SC_20002/SC_20102 reach the client promptly."""
    try:
        await _emit_task_progress(client, event_type, event_target, event_count)
        await client.flush()
    except Exception:
        pass


def schedule_emit(client: Client, event_type: int, event_target: int, event_count: int):
    """Fire emit_task_progress without blocking the caller. In production (an
    event loop is running) it is scheduled with create_task; in a synchronous
    test context (no running loop) it is run to completion in a throwaway loop
    so progress is still applied."""
    coro = emit_task_progress(client, event_type, event_target, event_count)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        loop.create_task(coro)
    else:
        try:
            asyncio.run(coro)
        except RuntimeError:
            pass


def _push_daily_reset(client: Client):
    """After a daily reset, push SC_20002 with progress=0 so the client UI
    refreshes the (now blank) daily tasks."""
    daily_ids = _get_daily_task_ids()
    if daily_ids:
        _push_progress_update(client, daily_ids)


def _send_day_proto(client: Client):
    """SC_20015 (dayProto) tells the client a new day started so it fires its
    DayCall (shop refresh, oil buy reset, etc.). The client ignores the body."""
    from src.protobuf import protobuf
    _send_message(client, 20015, protobuf.SC_20015(time=int(time.time())))


async def maybe_reset_daily_weekly(client: Client):
    """Called from the dispatch loop on every packet. Cheap: only does DB work
    and pushes when the region-local day or Monday-aligned week has changed
    since the last check for this client. This makes daily/weekly task reset
    happen live (while the player is online across a midnight boundary) without
    waiting for the next login."""
    if client.commander is None:
        return

    now = int(time.time())
    day_start = _region_day_start(now)
    last_day = getattr(client, "_reset_day_start", None)
    if last_day != day_start:
        store = get_default_store()
        if store is not None:
            try:
                _ensure_daily_tasks(store, client.commander.commander_id)
                _push_daily_reset(client)
                _send_day_proto(client)
            except Exception:
                pass
        client._reset_day_start = day_start

    week_bucket = _region_week_bucket_for(now)
    last_week = getattr(client, "_reset_week_bucket", None)
    if last_week != week_bucket:
        try:
            from src.answer.weekly_task_cluster import handle_weekly_missions as _weekly
            await _weekly(b"", client)
            await client.flush()
        except Exception:
            pass
        client._reset_week_bucket = week_bucket


def _region_week_bucket_for(now_ts: int) -> int:
    from src.answer.weekly_task_cluster import _region_week_bucket
    return _region_week_bucket(now_ts)


# ---------------------------------------------------------------------------
# Possession / state-based tasks
# ---------------------------------------------------------------------------

_POSSESSION_CACHE = None

def _build_possession_cache():
    """Per-task config for the possession/state-based sub_types that the
    client derives from its own data mirrors but the server must record.
    Returns a list of dicts (id, sub_type, target_id, target_id_2, target_num)
    seeded from task_data_template the same way _build_task_event_cache works.
    target_id/target_id_2 are kept RAW: for the level-based sub_types 1013/
    1017 they are lists (ship template ids / ship type ids), and only
    target_id_2 (1017) carries the required level — coercing them to int
    here made every "Get ... to Level 90" task check level >= 0."""
    global _POSSESSION_CACHE
    if _POSSESSION_CACHE is not None:
        return _POSSESSION_CACHE
    cache: list[dict] = []
    for tid, tpl in _all_task_templates().items():
        try:
            st = int(tpl.get("sub_type", 0) or 0)
        except (TypeError, ValueError):
            continue
        if st not in (
            44, 1011, 1013, 1017, 1026, 1027, 403, 1050, 85, 130, 194, 211,
            37, 47, 62, 83, 84, 99, 111, 112, 120, 136, 184, 192, 210, 1005, 1060,
            2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020
        ):
            continue
        cache.append({
            "id": int(tid),
            "sub_type": st,
            "type": int(tpl.get("type", 0) or 0),
            "target_id": tpl.get("target_id", 0),
            "target_id_2": tpl.get("target_id_2", "") or "",
            "target_num": _coerce_int(tpl.get("target_num", 0), 0),
        })
    _POSSESSION_CACHE = cache
    return cache


def _task_target_id_list(raw) -> list:
    """task_data_template target_id values may be a scalar id, a list of ids,
    or an empty Lua table / 0 meaning 'no filter'. Returns ints (0 dropped:
    it is never a valid ship type or template id)."""
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raw = [raw]
    out = []
    for v in raw:
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n > 0:
            out.append(n)
    return out


_SHIP_TYPE_CACHE: dict = {}

def _ship_type_for_task(template_id: int) -> int:
    """ship_data_statistics.type of a ship template (0 when unknown). The
    sub_type-1017 "Get any cruiser/carrier/..." tasks filter by this."""
    if template_id in _SHIP_TYPE_CACHE:
        return _SHIP_TYPE_CACHE[template_id]
    t = 0
    try:
        tpl = get_config_entry_sync("sharecfgdata/ship_data_statistics.json", str(template_id))
        if tpl is not None:
            d = tpl.data if isinstance(tpl.data, dict) else json.loads(tpl.data)
            t = int(d.get("type", 0) or 0)
    except Exception:
        t = 0
    _SHIP_TYPE_CACHE[template_id] = t
    return t


def _ship_rarity_for_task(ship_id: int) -> int:
    """Rarity (2..5) of a ship template from ship_data_statistics."""
    try:
        tpl = get_config_entry_sync("sharecfgdata/ship_data_statistics.json", str(ship_id))
    except Exception:
        tpl = None
    if tpl is None:
        return 0
    d = tpl.data if isinstance(tpl.data, dict) else None
    if d is None:
        return 0
    try:
        return int(d.get("rarity", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _pr_dr_template_ids() -> set:
    """Template ids of PR/DR (research) ships: every id listed in
    ShareCfg/ship_data_blueprint.json (keyed by blueprint id == ship template
    id in the EN data)."""
    global _PR_DR_CACHE
    if _PR_DR_CACHE is not None:
        return _PR_DR_CACHE
    ids: set = set()
    try:
        for e in list_config_entries_sync("ShareCfg/ship_data_blueprint.json"):
            try:
                ids.add(int(e.key))
            except (TypeError, ValueError):
                d = e.data if isinstance(e.data, dict) else {}
                if d.get("id") is not None:
                    try:
                        ids.add(int(d["id"]))
                    except (TypeError, ValueError):
                        pass
    except Exception:
        pass
    _PR_DR_CACHE = ids
    return ids


_PR_DR_CACHE = None
_EQUIP_RARITY_CACHE = None


def _sync_possession_tasks_sync(client: Client, _force: bool = False):
    """Recompute progress for possession/state-based tasks and UPDATE the rows.

    These tasks describe a STATE ("Possess N ships of level X", "own 3 Elite+
    gear", "join a guild", "reach 100 tech points") that the client derives
    from its own mirrors -- they are never advanced by discrete gameplay
    events. The server therefore syncs their progress rows (never exceeding
    target_num) at login and after dock/bag mutations, then pushes SC_20002
    for any row that changed. Rows are INSERTed in-progress (progress=0) if
    absent -- they only fill when the real state satisfies them -- and are
    never marked submitted (the player claims via CS_20005).

    Covered sub_types:
      44   "Possess N pieces of gear of rarity >= X"     (target_id = rarity;
            target_id_2 > 0 instead means "gear enhanced to Level target_id_2
            or higher" -- enhancement tier from equipments.level)
      1013 "Get <specific shipgirl(s)> to Level X"       (target_id = ship
            template id / list, target_num = the required level)
      1017 "Possess N shipgirls of <types> at Level X"   (target_id = ship
            type ids (empty = any), target_id_2 = the level, target_num = count)
      1026 "Gain N stars across Main Campaign stages"
      1027 "Possess 1 shipgirl at Limit Break stage X"   (target_id = stars)
      403  "Join any guild"
      1050 "Reach N Tech Points" (faction tech total)
      85   "Upgrade the Canteen or the Merchant to Level N" (Naval Academy
            oil/gold well levels; Handbook 22013+ / 23043)
      1011 "Reach Commander Level N"
      130  "Obtain a total of N Specialized Cores" (lifetime tally from
            commander_limit_items, incl. the month_bucket=0 lifetime bucket)
      194  "Possess N shipgirls with all stats enhanced to the max"
      211  "Obtain any PR/DR (research) shipgirl"
    """
    store = get_default_store()
    commander = getattr(client, "commander", None) if client is not None else None
    if store is None or commander is None:
        return
    commander_id = commander.commander_id

    cache = [
        t for t in _build_possession_cache()
        # Handbook (17) included: its rows are seeded by the manual seeder and
        # possession progress fills them. Event-family tasks (5/6/26/36/...)
        # must not gain rows here -- same rule as _emit_task_progress.
        if t.get("type", 0) in (SERVER_TRACKED_TASK_TYPES | {17})
    ]
    # Aggregate the needed state ONCE (shared across sub_types).
    ships = None
    if any(t["sub_type"] in (1013, 1017, 1027, 194, 211, 47, 62, 83, 120, 184, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020) for t in cache):
        try:
            from src.orm.owned_ship import list_dock_ships
            ships = list_dock_ships(commander_id)
        except Exception:
            ships = None

    def _ship_field(s, name):
        """Read a ship field from either an ORM row (attribute) or a dict."""
        if isinstance(s, dict):
            return s.get(name, 0) or 0
        return getattr(s, name, 0) or 0

    # sub_type 1027 "Possess 1 shipgirl at Limit Break stage X": the LB stage
    # is derived from max_level (breakout thresholds: 100 -> LB0, 110 -> LB1,
    # 120 -> LB2, 125 -> LB3).
    lb_stage_max = 0
    for s in ships or []:
        ml = int(_ship_field(s, "max_level") or 0)
        if ml >= 125:
            stage = 3
        elif ml >= 120:
            stage = 2
        elif ml >= 110:
            stage = 1
        else:
            stage = 0
        lb_stage_max = max(lb_stage_max, stage)

    # sub_type 44: gear rarity ownership (from owned_equipments + configs).
    gear_rarity_counts: dict[int, int] = {}
    try:
        rows = store.fetch(
            "SELECT equipment_id, count FROM owned_equipments WHERE commander_id = $1",
            commander_id,
        )
        for r in rows:
            eid = int(r[0] or 0)
            if eid <= 0:
                continue
            rarity = _equipment_rarity(eid)
            if rarity:
                gear_rarity_counts[rarity] = gear_rarity_counts.get(rarity, 0) + int(r[1] or 0)
    except Exception:
        pass
    # cumulative "rarity >= X" counts
    def _gear_at_least(min_rarity: int) -> int:
        return sum(n for rar, n in gear_rarity_counts.items() if rar >= min_rarity)

    # sub_type 1026: stars across campaign stages (chapter_progress star_rewarded)
    campaign_stars = 0
    try:
        state = _chapter_progress_state(commander_id)
        campaign_stars = sum(1 for cid, info in state.items() if info["star"] == 1 and cid < 1000000)
    except Exception:
        pass

    # sub_type 403: guild membership
    in_guild = 0
    try:
        row = store.fetchrow(
            "SELECT guild_id FROM guild_members WHERE commander_id = $1 LIMIT 1",
            commander_id,
        )
        in_guild = 1 if row is not None else 0
    except Exception:
        pass

    # sub_type 1050: total faction tech points
    tech_total = 0
    try:
        from src.answer.shipyard_blueprint_helpers import compute_faction_tech_points
        tech_total = sum(int(v or 0) for v in compute_faction_tech_points(commander_id).values())
    except Exception:
        pass

    # sub_type 1011: commander level.
    commander_level = int(getattr(commander, "level", 0) or 0)

    # sub_type 85: Naval Academy Canteen (oil well) / Merchant (gold well)
    # levels. An upgrade whose completion time has already passed but whose
    # level bump has not been normalized yet counts as reached.
    academy_max_level = 0
    class_room_level = 1
    try:
        from src.orm.naval_academy_runtime import load_naval_academy_runtime
        import time as _time
        rt = load_naval_academy_runtime(commander_id)
        if rt is not None:
            class_room_level = int(getattr(rt, "class_room_level", 1) or 1)
            now_unix = int(_time.time())
            for level, finish in (
                (int(rt.oil_well_level or 0), int(rt.oil_upgrade_complete_time or 0)),
                (int(rt.gold_well_level or 0), int(rt.gold_upgrade_complete_time or 0)),
            ):
                if finish > 0 and finish <= now_unix:
                    level += 1
                academy_max_level = max(academy_max_level, level)
    except Exception:
        pass

    # sub_type 130: lifetime "Obtain N Specialized Cores" tally (all buckets of
    # commander_limit_items, including the month_bucket=0 lifetime bucket that
    # add_limit_item maintains alongside the monthly one).
    core_lifetime = 0
    if any(t["sub_type"] == 130 for t in cache):
        try:
            from src.orm.limit_item import SPECIALIZED_CORE_ITEM_ID
            row = store.fetchrow(
                "SELECT COALESCE(SUM(count), 0) FROM commander_limit_items "
                "WHERE commander_id = $1 AND item_id = $2",
                commander_id, SPECIALIZED_CORE_ITEM_ID,
            )
            core_lifetime = int(row[0] or 0) if row is not None else 0
        except Exception:
            pass

    # sub_type 211: PR/DR (research) ships owned (matched on base template id).
    pr_dr_owned = 0
    # sub_type 194: ships with every enhanceable stat at its cap (cap computed
    # exactly like mod_ship does: top_limit(level, durability) * level_exp).
    full_enhanced = 0
    if ships is not None and any(t["sub_type"] in (194, 211) for t in cache):
        pr_dr_ids = _pr_dr_template_ids()
        if any(t["sub_type"] == 194 for t in cache):
            try:
                from src.orm.game_data import get_ship_template_config, get_ship_strengthen_config
                from src.answer.mod_ship import _ship_mod_top_limit, SHIP_MOD_STRENGTH_IDS
                from src.orm.owned_ship_strength import list_all_owned_ship_strengths

                exps_by_ship: dict[int, dict[int, int]] = {}
                try:
                    for r in list_all_owned_ship_strengths(
                        commander_id, [int(_ship_field(s, "id") or 0) for s in ships]
                    ):
                        exps_by_ship.setdefault(int(r.ship_id), {})[int(r.strength_id)] = int(r.exp or 0)
                except Exception:
                    exps_by_ship = {}
                strengthen_cache: dict[int, Optional[dict]] = {}

                for s in ships:
                    sid = int(_ship_field(s, "ship_id") or 0)
                    if pr_dr_ids and (sid in pr_dr_ids or (sid // 10) in pr_dr_ids):
                        pr_dr_owned += 1
                    if sid <= 0:
                        continue
                    exps = exps_by_ship.get(int(_ship_field(s, "id") or 0))
                    if not exps:
                        continue
                    # cap per stat mirrors _ship_mod_strength_updates exactly
                    if sid not in strengthen_cache:
                        try:
                            tpl = get_ship_template_config(sid)
                            strengthen_cache[sid] = (
                                get_ship_strengthen_config(tpl["strengthen_id"])
                                if tpl is not None else None
                            )
                        except Exception:
                            strengthen_cache[sid] = None
                    cfg = strengthen_cache[sid]
                    if not isinstance(cfg, dict):
                        continue
                    durability = cfg.get("durability") or []
                    level_exp = cfg.get("level_exp") or []
                    if len(durability) < len(SHIP_MOD_STRENGTH_IDS) or len(level_exp) < len(SHIP_MOD_STRENGTH_IDS):
                        continue
                    level = int(_ship_field(s, "level") or 0)
                    checked = 0
                    maxed = True
                    for index, strength_id in enumerate(SHIP_MOD_STRENGTH_IDS):
                        top_limit = _ship_mod_top_limit(level, durability[index])
                        if top_limit <= 0:
                            continue
                        ratio = level_exp[index] or 1
                        if exps.get(strength_id, 0) < top_limit * ratio:
                            maxed = False
                            break
                        checked += 1
                    if maxed and checked > 0:
                        full_enhanced += 1
            except Exception:
                pass
        else:
            for s in ships:
                sid = int(_ship_field(s, "ship_id") or 0)
                if sid > 0 and pr_dr_ids and (sid in pr_dr_ids or (sid // 10) in pr_dr_ids):
                    pr_dr_owned += 1

    has_submarine = any(_ship_type_for_task(int(_ship_field(s, "ship_id") or 0)) in (8, 14, 22) for s in (ships or []))
    has_lb3_lv100 = any(int(_ship_field(s, "level") or 0) >= 100 and int(_ship_field(s, "max_level") or 0) >= 100 for s in (ships or []))
    has_fleet = 1 if (ships and len(ships) > 0) else 0
    has_dorm_ship = any(int(_ship_field(s, "state") or 0) in (2, 5) for s in (ships or []))

    has_skin_equipped = 0
    equipped_gear_count = 0
    if any(t["sub_type"] in (47, 1060) for t in cache):
        try:
            erow = store.fetchrow(
                "SELECT SUM(CASE WHEN equip_id > 0 THEN 1 ELSE 0 END), "
                "       SUM(CASE WHEN skin_id > 0 THEN 1 ELSE 0 END) "
                "FROM owned_ship_equipments WHERE owner_id = $1",
                commander_id,
            )
            on_ships = int(erow[0] or 0) if erow else 0
            has_skin_equipped = 1 if (erow and int(erow[1] or 0) > 0) else 0
            in_depot = int(store.fetchval("SELECT COALESCE(SUM(count), 0) FROM owned_equipments WHERE commander_id = $1", commander_id) or 0)
            equipped_gear_count = on_ships + in_depot
        except Exception:
            pass

    owned_stories = set()
    if any(t["sub_type"] == 1005 for t in cache):
        try:
            srows = store.fetch("SELECT story_id FROM commander_stories WHERE commander_id = $1", commander_id)
            owned_stories = {int(r[0]) for r in srows if r and r[0] is not None}
        except Exception:
            owned_stories = set()

    has_collected_mail = 0
    if any(t["sub_type"] == 136 for t in cache):
        try:
            crow = store.fetchval("SELECT COUNT(*) FROM mails WHERE receiver_id = $1 AND attachments_collected = true", commander_id)
            has_collected_mail = 1 if int(crow or 0) > 0 else 0
        except Exception:
            has_collected_mail = 0

    tech_started = 0
    tech_focus = 0
    if any(t["sub_type"] in (111, 112) for t in cache):
        try:
            trow = store.fetchrow(
                "SELECT catchup_target, queue, refresh_pools FROM technology_research_states WHERE commander_id = $1",
                commander_id,
            )
            if trow:
                ctarget = int(trow[0] or 0)
                q_data = trow[1]
                pools_data = trow[2]
                if ctarget > 0:
                    tech_focus = 1
                if pools_data:
                    p_list = pools_data if isinstance(pools_data, list) else json.loads(pools_data) if isinstance(pools_data, str) else []
                    for p in p_list:
                        if p.get("target", 0) > 0:
                            tech_focus = 1
                        for proj in p.get("technologies", []):
                            if proj.get("finish_time", 0) > 0:
                                tech_started = 1
                if q_data:
                    q_list = q_data if isinstance(q_data, list) else json.loads(q_data) if isinstance(q_data, str) else []
                    if len(q_list) > 0:
                        tech_started = 1
        except Exception:
            pass

    pr_dev_started = 1 if pr_dr_owned > 0 else 0
    if not pr_dev_started and any(t["sub_type"] in (99, 210) for t in cache):
        try:
            s_rows = store.fetch("SELECT start_time, ship_id FROM commander_shipyard_blueprints WHERE commander_id = $1", commander_id)
            for sr in (s_rows or []):
                if int(sr[0] or 0) > 0 or int(sr[1] or 0) > 0:
                    pr_dev_started = 1
                    break
        except Exception:
            pass

    max_skill_level = 1
    if any(t["sub_type"] == 37 for t in cache):
        try:
            slvl = store.fetchval("SELECT MAX(level) FROM commander_ship_skills WHERE commander_id = $1", commander_id)
            max_skill_level = int(slvl or 1)
        except Exception:
            max_skill_level = 1

    has_requisition = 0
    if any(t["sub_type"] == 192 for t in cache):
        try:
            rrow = store.fetchrow(
                "SELECT support_requisition_count, support_requisition_month FROM commanders WHERE commander_id = $1",
                commander_id,
            )
            if rrow and (int(rrow[0] or 0) > 0 or int(rrow[1] or 0) > 0):
                has_requisition = 1
        except Exception:
            has_requisition = 0

    computed: dict[tuple, int] = {}
    downgradable: set[int] = set()
    # 1013/1017 progress mirrors the dock exactly, so it must be able to move
    # DOWN (the coercion bug wrote progress=1 into unclaimed Level-90 rows).
    # But a failed dock load must not wipe those rows to 0 either — skip the
    # two sub_types entirely when the dock is unavailable.
    level_types_ready = ships is not None
    for task in cache:
        st = task["sub_type"]
        tid = task["id"]
        tn = task["target_num"]
        if tn <= 0:
            continue
        if st == 1013:
            # target_id = ship base template id / list / 0 (any ship);
            # target_num = the required level. Progress = the best matching
            # ship's level capped at target_num, so the client's "67/90" bar
            # tracks real progress. owned_ships.ship_id stores the modern
            # variant id (base*10 + star digit: 201213 = Javelin at 4 stars)
            # while the task config targets the BASE id (20121), so match on
            # ship_id // 10 as well as the raw id.
            if not level_types_ready:
                continue
            ids = set(_task_target_id_list(task["target_id"]))
            best = 0
            for s in ships:
                sid = int(_ship_field(s, "ship_id") or 0)
                if ids and sid not in ids and (sid // 10) not in ids:
                    continue
                best = max(best, int(_ship_field(s, "level") or 0))
                if best >= tn:
                    break
            computed[(tid, tn)] = min(best, tn)
            downgradable.add(tid)
        elif st == 1017:
            # target_id = ship type ids (empty -> any type); target_id_2 = the
            # required level; target_num = how many ships must qualify.
            if not level_types_ready:
                continue
            lvl = _coerce_int(task["target_id_2"], 0)
            if lvl <= 0:
                lvl = 1
            types = set(_task_target_id_list(task["target_id"]))
            count = 0
            for s in ships:
                if types and _ship_type_for_task(int(_ship_field(s, "ship_id") or 0)) not in types:
                    continue
                if int(_ship_field(s, "level") or 0) >= lvl:
                    count += 1
            computed[(tid, tn)] = min(count, tn)
            downgradable.add(tid)
        elif st == 44:
            tg = _coerce_int(task["target_id"], 0)
            lvl_req = _coerce_int(task["target_id_2"], 0)
            if lvl_req > 0:
                # "N pieces of gear enhanced to Level <lvl_req> or higher"
                # (Rookie 22074/22097, Guide 23052: target_id_2=8). The
                # enhancement tier of a gear id lives in equipments.level;
                # owned_equipments only holds (equipment_id, count).
                lvl_count = 0
                try:
                    lrow = store.fetchrow(
                        "SELECT COALESCE(SUM(oe.count), 0) "
                        "FROM owned_equipments oe "
                        "JOIN equipments e ON e.id = oe.equipment_id "
                        "WHERE oe.commander_id = $1 AND e.level >= $2",
                        commander_id, lvl_req,
                    )
                    lvl_count = int(lrow[0] or 0) if lrow is not None else 0
                except Exception:
                    pass
                computed[(tid, tn)] = min(lvl_count, tn)
            else:
                computed[(tid, tn)] = min(_gear_at_least(tg or 3), tn)
        elif st == 1027:
            tg = _coerce_int(task["target_id"], 0)
            computed[(tid, tn)] = 1 if lb_stage_max >= (tg or 1) else 0
        elif st == 1026:
            computed[(tid, tn)] = min(campaign_stars, tn)
        elif st == 403:
            computed[(tid, tn)] = in_guild
        elif st == 1050:
            computed[(tid, tn)] = min(tech_total, tn)
        elif st == 1011:
            computed[(tid, tn)] = min(commander_level, tn)
        elif st == 85:
            computed[(tid, tn)] = min(academy_max_level, tn)
        elif st == 130:
            computed[(tid, tn)] = min(core_lifetime, tn)
        elif st == 211:
            computed[(tid, tn)] = min(pr_dr_owned, tn)
        elif st == 194:
            computed[(tid, tn)] = min(full_enhanced, tn)
        elif st == 1005:
            sids = set(_task_target_id_list(task["target_id"]))
            matched = sum(1 for sid in sids if sid in owned_stories)
            computed[(tid, tn)] = min(matched, tn)
        elif st == 184:
            computed[(tid, tn)] = 1 if has_submarine else 0
        elif st == 83:
            computed[(tid, tn)] = tn if has_lb3_lv100 else 0
        elif st == 84:
            computed[(tid, tn)] = min(class_room_level, tn)
        elif st == 1060:
            computed[(tid, tn)] = min(equipped_gear_count, tn)
        elif st == 47:
            computed[(tid, tn)] = 1 if has_skin_equipped else 0
        elif st == 62:
            computed[(tid, tn)] = 1 if has_dorm_ship else 0
        elif st == 136:
            computed[(tid, tn)] = has_collected_mail
        elif st == 210:
            computed[(tid, tn)] = pr_dev_started
        elif st == 99:
            computed[(tid, tn)] = tn if pr_dr_owned > 0 else (1 if pr_dev_started else 0)
        elif st == 111:
            computed[(tid, tn)] = tech_started
        elif st == 112:
            computed[(tid, tn)] = tech_focus
        elif st == 120:
            tids_120 = set(_task_target_id_list(task["target_id"]))
            ok_120 = False
            if 15008 in tids_120 or 15012 in tids_120:
                ok_120 = any(int(_ship_field(s, "max_level") or 0) > 100 for s in (ships or []))
            elif 16501 in tids_120 or 16502 in tids_120 or 16503 in tids_120:
                ok_120 = any(int(_ship_field(s, "level") or 0) >= 2 for s in (ships or []))
            elif 15003 in tids_120:
                ok_120 = len(ships or []) >= 2
            if ok_120:
                computed[(tid, tn)] = tn
        elif st in (2013, 2014, 2015, 2016, 2017, 2019, 2020):
            computed[(tid, tn)] = has_fleet
        elif st == 2018:
            computed[(tid, tn)] = 1 if has_submarine else 0
        elif st == 37:
            computed[(tid, tn)] = min(max_skill_level, tn)
        elif st == 192:
            computed[(tid, tn)] = min(has_requisition, tn)

    if not computed:
        return

    # Read existing rows in ONE query.
    tids = [t for (t, _n) in computed]
    existing = fetch_commander_task_progress_map(commander_id, tids)

    changed: list[tuple[int, int]] = []
    to_insert = []
    to_update = []
    now_ts = int(time.time())
    for (tid, tn), value in computed.items():
        cur = existing.get(tid)
        if cur is None:
            to_insert.append((commander_id, tid, value, now_ts))
            if value > 0:
                changed.append((tid, value))
        elif value != cur and (tid in downgradable or value > cur):
            to_update.append((value, commander_id, tid))
            changed.append((tid, value))

    if to_insert:
        try:
            store.executemany(
                "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
                "VALUES ($1, $2, $3, $4, 0) ON CONFLICT (commander_id, task_id) DO NOTHING",
                to_insert,
            )
        except Exception:
            pass
    if to_update:
        try:
            store.executemany(
                "UPDATE commander_tasks SET progress = $1 "
                "WHERE commander_id = $2 AND task_id = $3 AND submit_time = 0",
                to_update,
            )
        except Exception:
            pass

    if changed:
        try:
            # Direct push (not _push_progress_update): filter out sub-tasks of
            # locked Handbook pages the same way -- their progress stays in the
            # DB and reaches the client only after the page unlocks.
            from src.answer.commandermisc.handlers import _locked_manual_subtask_ids
            locked = _locked_manual_subtask_ids(client, get_default_store(), commander_id)
            if locked:
                changed = [(tid, value) for (tid, value) in changed if tid not in locked]
        except Exception:
            locked = set()
        if not changed:
            return
        try:
            from src.protobuf import protobuf
            resp = protobuf.SC_20002()
            for (tid, value) in changed:
                resp.info.append(protobuf.TASK_PROGRESS(id=tid, progress=value))
            _send_message(client, 20002, resp)
        except Exception:
            pass


def schedule_possession_sync(client: Client, force: bool = False):
    """Fire _sync_possession_tasks_sync off the response path (mirrors
    schedule_emit). Safe to call from sync handlers; never raises."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        loop.create_task(asyncio.to_thread(_sync_possession_tasks_sync, client, force))
    else:
        try:
            _sync_possession_tasks_sync(client, force)
        except Exception:
            pass


def _equipment_rarity(equipment_id: int) -> int:
    """Rarity (2..5) of a gear id. The `equipments` table has no rarity column,
    so read it from the raw sharecfgdata/equip_data_statistics.json mirror
    (data.rarity). Cached per process."""
    global _EQUIP_RARITY_CACHE
    if _EQUIP_RARITY_CACHE is None:
        _EQUIP_RARITY_CACHE = {}
    cache = _EQUIP_RARITY_CACHE
    if equipment_id in cache:
        return cache[equipment_id]
    rarity = 0
    try:
        tpl = get_config_entry_sync("sharecfgdata/equip_data_statistics.json", str(equipment_id))
        if tpl is not None:
            d = tpl.data if isinstance(tpl.data, dict) else json.loads(tpl.data)
            rarity = int(d.get("rarity", 0) or 0)
            if not rarity and d.get("base"):
                base_tpl = get_config_entry_sync("sharecfgdata/equip_data_statistics.json", str(d.get("base")))
                if base_tpl is not None:
                    base_d = base_tpl.data if isinstance(base_tpl.data, dict) else json.loads(base_tpl.data)
                    rarity = int(base_d.get("rarity", 0) or 0)
    except Exception:
        rarity = 0
    cache[equipment_id] = rarity
    return rarity
