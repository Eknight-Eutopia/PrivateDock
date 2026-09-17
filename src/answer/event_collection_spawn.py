from __future__ import annotations

import asyncio
import json
import random
import time
from pathlib import Path
from typing import Optional

from src.orm import event_collection as ec

DAILY_POOL_SIZE = 8

DAILY_RESOURCE_EXTRACTION_PER_DAY = 10

NIGHT_COMMISSIONS_PER_WINDOW = 4

URGENT_SPAWN_CHANCE_PERCENT = 3

URGENT_ACTIVE_CAP = 5
# Shelf life when the template carries no `time` of its own.
URGENT_FALLBACK_EXPIRE_SECONDS = 2 * 3600

# Daily board cards draw ONLY from these categories: the 1-2h Daily Resource
# Extraction commissions (first 10/day) and the Extra commissions. Night
# commissions belong to the URGENT tab (4 per night window) and Major
# (rollover) commissions exist exactly one at a time — neither is part of the
# random daily mix.
DAILY_CATEGORIES = ["daily_resource_extraction", "extra"]
NIGHT_CATEGORY = "night"
MAJOR_CATEGORY = "major"
URGENT_CATEGORIES = ["urgent"]

# Real night commissions (EN collection_template type == 5, EVENT_TYPE_NIGHT).
# The client's urgent tab (eventlistscene.Flush -> EventProxy:checkNightEvent)
# flushes CS_13009 forever unless eventDic contains at least one type-5
# commission with a live countdown. Must always be topped up during the night
# window (see refresh_commissions_sync).
NIGHT_COMMISSION_IDS = {
    40101, 40102, 40103, 40104, 40105, 40106,
    40201, 40202, 40203, 40204, 40205, 40206,
    40301, 40302, 40303, 40304, 40305, 40306,
}

# Lifetime of an unstarted daily commission before it disappears.
DAILY_EXPIRE_MIN_SECONDS = 6 * 3600
DAILY_EXPIRE_MAX_SECONDS = 12 * 3600

# Lifetime of an unstarted urgent commission spawned outside the night window
# (battle drops) when its template has no `time` of its own.
URGENT_EXPIRE_MIN_SECONDS = 2 * 3600
URGENT_EXPIRE_MAX_SECONDS = 4 * 3600

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configurations" / "commission_ids.json"
_POOLS_CACHE: Optional[dict] = None


def _load_commission_pools() -> dict:
    global _POOLS_CACHE
    if _POOLS_CACHE is not None:
        return _POOLS_CACHE
    data: dict = {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    _POOLS_CACHE = data
    return data


def reload_commission_pools():
    global _POOLS_CACHE
    _POOLS_CACHE = None


def eligible_ids(categories: list[str], player_level: int) -> list[int]:
    """All template ids in `categories` whose unlock level <= player_level."""
    pools = _load_commission_pools()
    out: list[int] = []
    for cat in categories:
        levels = pools.get(cat)
        if not levels:
            continue
        for lv_str, ids in levels.items():
            try:
                lv = int(lv_str)
            except (TypeError, ValueError):
                continue
            if lv <= player_level:
                out.extend(ids)
    return out


def _random_expiry(min_s: int, max_s: int) -> int:
    return int(time.time()) + random.randint(min_s, max_s)


def _load_collection_template(collection_id: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        raw = get_config_entry("ShareCfg/collection_template.json", str(collection_id))
    except NotFoundError:
        return None
    except Exception:
        return None
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "data"):
        raw = raw.data
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if isinstance(raw, str) else None
    except Exception:
        return None


def _insert_and_get_sync(commander_id: int, commission_id: int, ctype: int,
                         expires_at: int) -> "ec.EventCollection":
    now = int(time.time())
    row_id = ec.insert_commission_sync(
        commander_id=commander_id,
        commission_id=commission_id,
        ctype=ctype,
        state=ec.STATE_AVAILABLE,
        ship_ids=[],
        spawn_time=now,
        expires_at=expires_at,
        created_at=now,
    )
    return ec.get_commission_sync(row_id)


def _pick_and_spawn(commander_id: int, categories: list[str], ctype: int,
                    player_level: int, existing: set, min_expire: int, max_expire: int):
    """Pick a random eligible template not already present for the commander and
    spawn it. Returns the new EventCollection row, or None if nothing eligible."""
    ids = [i for i in eligible_ids(categories, player_level) if i not in existing]
    if not ids:
        return None
    chosen = random.choice(ids)
    return _insert_and_get_sync(commander_id, chosen, ctype, _random_expiry(min_expire, max_expire))


def is_night_window_open() -> bool:
    """Whether the client's night-commission window is currently open.

    The client (EN/model/proxy/eventproxy.lua checkNightEvent) opens the night
    tab only while the *server* clock is within [night_collection_begin=19,
    night_collection_end=3] (gameset). Night commissions are added to players
    during this window but are displayed at any time once present. Use the
    region's local time so non-UTC regions stay correct.
    """
    from src.region import region
    now = region.local_now()
    # fractional hour for sub-hour precision
    hour = now.hour + now.minute / 60.0 + now.second / 3600.0
    begin, end = 19.0, 3.0
    # window wraps midnight: open if hour >= begin OR hour < end
    return hour >= begin or hour < end


def _next_night_window_end_ts() -> int:
    """Absolute server-local timestamp of the next night-window close (03:00).

    Used as the over_time for *available* night commissions so the client's
    countdown ("disappears in Nh") matches when the server actually clears
    them at window close (see refresh_commissions_sync). Matches official,
    where night commissions live only until the window ends."""
    from src.region import region
    from datetime import timedelta
    now = region.local_now()
    end = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if now.hour >= 3:
        end = end + timedelta(days=1)
    return int(end.timestamp())


def _spawn_night_sync(commander_id: int, commission_id: int, ctype: int):
    """Spawn an available night commission whose over_time is the window close
    (not a random 6-12h), so its disappearance lines up with the server's
    window-based cleanup."""
    return _insert_and_get_sync(commander_id, commission_id, ctype, _next_night_window_end_ts())


def _daily_resource_generated_today_sync(commander_id: int) -> int:
    """How many Daily Resource Extraction commissions were generated for this
    commander since the region's daily reset (wiki: the first 10 dailies
    generated in a day are of this type)."""
    from src.shopreset.framework import daily_window
    ids = eligible_ids(["daily_resource_extraction"], 999)
    return ec.count_spawned_since_sync(commander_id, ids, daily_window().key)


def _spawn_one_daily_sync(commander_id: int, player_level: int, existing: set):
    """Spawn the next daily board card, honouring the resource-extraction-first
    rule: before 10 resource extractions have been generated today, the card is
    a Daily Resource Extraction commission; afterwards it is an Extra one.
    Falls back to the other category when the preferred pool is exhausted
    (all its templates already on the board / above the player level)."""
    resource_today = _daily_resource_generated_today_sync(commander_id)
    prefer = ["daily_resource_extraction", "extra"] if resource_today < DAILY_RESOURCE_EXTRACTION_PER_DAY \
        else ["extra", "daily_resource_extraction"]
    for cat in prefer:
        row = _pick_and_spawn(
            commander_id, [cat], ec.TYPE_DAILY, player_level, existing,
            DAILY_EXPIRE_MIN_SECONDS, DAILY_EXPIRE_MAX_SECONDS,
        )
        if row is not None:
            return row
    return None


def _ensure_major_sync(commander_id: int, player_level: int, rows) -> Optional["ec.EventCollection"]:
    """Wiki ("Major commissions"): "Exactly one of these commissions is
    available (or in progress) at any given time, with a new one generated on
    completion." The rollover commission never expires on its own
    (expires_at = 0, the client treats over_time == 0 as "no countdown")."""
    major_ids = set(eligible_ids([MAJOR_CATEGORY], 999))
    if any(r.commission_id in major_ids for r in rows):
        return None
    chosen_ids = [i for i in eligible_ids([MAJOR_CATEGORY], player_level)]
    if not chosen_ids:
        return None
    chosen = random.choice(chosen_ids)
    return _insert_and_get_sync(commander_id, chosen, ec.TYPE_DAILY, 0)


def _push_new_commissions(client, new_rows: list) -> None:
    """Push SC_13011 so the running client learns about newly spawned
    commissions without reopening the board (EventProxy.on(13011) ->
    updateInfoList, and eventForMsg shows the "new commission" notification)."""
    if not new_rows:
        return
    from src.protobuf import protobuf
    update = protobuf.SC_13011()
    for row in new_rows:
        col = protobuf.COLLECTIONINFO(
            id=row.commission_id,
            finish_time=row.finish_time or 0,
            over_time=row.expires_at or 0,
        )
        for sid in (row.ship_ids or []):
            col.ship_id_list.append(int(sid))
        update.collection.append(col)
    asyncio.create_task(client.send_message(13011, update))


def refresh_commissions_sync(client) -> list:
    """Clean expired offers and rebuild the daily/night/major pools.

    Called on board open (SC_13002) and on the client's flush (CS_13009).
    Returns the commander's current commission rows.

    Does NOT push SC_13011 (originally does not: login is SC_13001+SC_13002 only
    , and the CS_13009 flush reply SC_13010 already carries the full list, which
    the client applies via EventProxy:updateAll). SC_13011 is reserved for the
    mid-session urgent spawn after a campaign battle victory — the only push
    that legitimately triggers the client's "Urgent Commission: <title>!"
    msgbox (eventForMsg).

    NOTE: the client renders each commission by looking up
    `pg.collection_template[id]`, so the wire `id` is the *template* id
    (commission_id), never the surrogate row id. To keep server-side lookups
    unambiguous we never keep two active rows with the same commission_id for
    one commander (no-duplicate rule below).
    """
    cid = client.commander.commander_id
    level = getattr(client.commander, "level", 1) or 1
    now = int(time.time())

    ec.delete_expired_available_sync(cid, now)

    rows = ec.list_commissions_sync(cid)
    new_rows: list = []

    window_open = is_night_window_open()

    # Daily board: 4 Daily + 4 Rollover cards (DAILY_POOL_SIZE), drawn from the
    # resource-extraction-first daily mix. Night commissions are NOT part of
    # the daily board — officially they appear in the Urgent tab (see below).
    existing = {r.commission_id for r in rows}
    avail_daily = sum(1 for r in rows if r.type == ec.TYPE_DAILY and r.state == ec.STATE_AVAILABLE)
    while avail_daily < DAILY_POOL_SIZE:
        row = _spawn_one_daily_sync(cid, level, existing)
        if row is None:
            break
        rows.append(row)
        new_rows.append(row)
        existing.add(row.commission_id)
        avail_daily += 1

    # Night commissions (type 5, Urgent tab): four appear automatically during
    # the client's night window (gameset night_collection_begin/end) and live
    # until the window closes. Outside the window do not spawn them; their
    # over_time is set to the window close (see _spawn_night_sync), so they
    # disappear naturally at window end — the client hides an available
    # commission once over_time passes (StateExpire) and the existing
    # delete_expired_available_sync garbage-collects the row. Spawned with the
    # TYPE_URGENT spawn class: they do not occupy daily board slots.
    if window_open:
        avail_night = sum(
            1 for r in rows
            if r.commission_id in NIGHT_COMMISSION_IDS
            and r.state == ec.STATE_AVAILABLE
        )
        while avail_night < NIGHT_COMMISSIONS_PER_WINDOW:
            ids = [i for i in eligible_ids([NIGHT_CATEGORY], level) if i not in existing]
            if not ids:
                break
            row = _spawn_night_sync(cid, random.choice(ids), ec.TYPE_URGENT)
            rows.append(row)
            new_rows.append(row)
            existing.add(row.commission_id)
            avail_night += 1

    # Major (rollover) commission: exactly one available-or-in-progress at any
    # given time; a new one appears when the previous is collected.
    major_row = _ensure_major_sync(cid, level, rows)
    if major_row is not None:
        rows.append(major_row)
        new_rows.append(major_row)

    return rows


def spawn_daily_on_complete_sync(client) -> list:
    """Wiki: "A new Commission is generated when a Daily is completed."
    Spawn one extra daily card after a successful collection (also keeps the
    exactly-one Major invariant). The caller delivers the new rows to the
    client inside SC_13006.new_collection — official never pushes SC_13011 for
    a replacement daily (four CS_13005 collects each answered by SC_13006
    alone, carrying new_collection; SC_13011 only ever follows a campaign
    battle victory). Pushing it here would fire the client's "Urgent
    Commission: <title>!" msgbox (levelmediator2 OnEventUpdate ->
    event_special_update) for a plain daily card. Returns the newly spawned
    rows."""
    cid = client.commander.commander_id
    level = getattr(client.commander, "level", 1) or 1
    rows = ec.list_commissions_sync(cid)
    existing = {r.commission_id for r in rows}
    new_rows: list = []

    row = _spawn_one_daily_sync(cid, level, existing)
    if row is not None:
        rows.append(row)
        new_rows.append(row)
        existing.add(row.commission_id)

    major_row = _ensure_major_sync(cid, level, rows)
    if major_row is not None:
        new_rows.append(major_row)

    return new_rows


def maybe_spawn_urgent_after_battle_sync(client, stage_id: int) -> bool:
    """Wiki ("Urgent Commissions"): "When finishing a Campaign battle, there is
    a chance for one of these Commissions to appear." Called after a victorious
    battle; only campaign (chapter) battles roll. The new offer is pushed via
    SC_13011 so it shows up in the Urgent tab immediately, with its countdown
    taken from the template's own `time` shelf life."""
    from src.config.game_variables import get_urgent_commission_spawn_chance_percent
    if random.randint(1, 100) > get_urgent_commission_spawn_chance_percent():
        return False

    cid = client.commander.commander_id
    level = getattr(client.commander, "level", 1) or 1

    # Only campaign (chapter) battles spawn urgents — daily challenges, event
    # stages and duels do not (the same test the chapter writeback uses).
    if stage_id:
        try:
            from src.orm.chapter import get_chapter_state_sync
            from src.protobuf import protobuf as _pb
            from src.answer.battle_session import _is_chapter_battle
            state = get_chapter_state_sync(cid)
            if state is None or not state.state:
                return False
            current = _pb.CURRENTCHAPTERINFO()
            current.ParseFromString(bytes(state.state))
            if not _is_chapter_battle(current, stage_id):
                return False
        except Exception:
            return False

    rows = ec.list_commissions_sync(cid)
    existing = {r.commission_id for r in rows}

    # Cap concurrent urgent-tab offers (battle drops + night commissions).
    urgent_active = sum(
        1 for r in rows
        if r.type == ec.TYPE_URGENT and r.state == ec.STATE_AVAILABLE
    )
    if urgent_active >= URGENT_ACTIVE_CAP:
        return False

    ids = [i for i in eligible_ids(URGENT_CATEGORIES, level) if i not in existing]
    if not ids:
        return False
    chosen = random.choice(ids)

    # Shelf life: the template's own `time` (e.g. 7200 = disappears in 2h);
    # falls back to a fixed window when the template carries none.
    template = _load_collection_template(chosen)
    shelf = int((template or {}).get("time", 0) or 0)
    if shelf <= 0:
        expires_at = _random_expiry(URGENT_EXPIRE_MIN_SECONDS, URGENT_EXPIRE_MAX_SECONDS)
    else:
        expires_at = int(time.time()) + shelf

    row = _insert_and_get_sync(cid, chosen, ec.TYPE_URGENT, expires_at)
    _push_new_commissions(client, [row])
    return True
