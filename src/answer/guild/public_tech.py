from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from src.db.store import get_default_store
from src.orm.config_entry import fetch_config_entries_data, fetch_config_entry_data
from src.protobuf import protobuf
from src.orm.resource import (
    has_enough_resource_async,
    consume_resource_async,
    add_resource,
)
from src.orm.item import has_enough_item, consume_item
from src.shopreset.framework import deterministic_seed, daily_window
from src.rng.rng import LockedRand
from src.logger.logger import log_event, LOG_LEVEL_ERROR

GUILD_COIN_RES = 8
GOLD_RES = 1

# Task sub_type for "Contribute X times to your Guild Logistics" missions
# (task_data_template entries such as id 7206 / 56061 use sub_type 402).
GUILD_LOGISTICS_DONATE_EVENT = 402

TECH_CATEGORY = "ShareCfg/guild_technology_template.json"
CONTRIB_CATEGORY = "ShareCfg/guild_contribution_template.json"
GUILDSET_CATEGORY = "ShareCfg/guildset.json"

_TECH_CACHE: Optional[dict] = None
_CONTRIB_CACHE: Optional[dict] = None
_GROUP_FIRST_CACHE: Optional[dict] = None
_GROUP_MAX_CACHE: Optional[dict] = None


def _load_json_config(category: str) -> dict:
    out = {}
    for d in fetch_config_entries_data(category):
        if isinstance(d, dict) and d and "id" in d:
            out[d["id"]] = d
    return out


def _tech_map() -> dict:
    global _TECH_CACHE
    if _TECH_CACHE is None:
        _TECH_CACHE = _load_json_config(TECH_CATEGORY)
    return _TECH_CACHE


def _contrib_map() -> dict:
    global _CONTRIB_CACHE
    if _CONTRIB_CACHE is None:
        _CONTRIB_CACHE = _load_json_config(CONTRIB_CATEGORY)
    return _CONTRIB_CACHE


def _group_first_tech() -> dict:
    global _GROUP_FIRST_CACHE
    if _GROUP_FIRST_CACHE is None:
        m = _tech_map()
        groups = {}
        for tid, d in m.items():
            g = d.get("group")
            groups.setdefault(g, []).append(tid)
        _GROUP_FIRST_CACHE = {g: min(ids) for g, ids in groups.items()}
    return _GROUP_FIRST_CACHE


def _group_max_tech() -> dict:
    global _GROUP_MAX_CACHE
    if _GROUP_MAX_CACHE is None:
        m = _tech_map()
        out = {}
        for g, first in _group_first_tech().items():
            cur = first
            seen = set()
            while cur and cur not in seen:
                seen.add(cur)
                nxt = m.get(cur, {}).get("next_tech", 0)
                if not nxt:
                    break
                cur = nxt
            out[g] = cur
        _GROUP_MAX_CACHE = out
    return _GROUP_MAX_CACHE


def _day_key() -> int:
    try:
        return int(daily_window(datetime.now(timezone.utc)).key)
    except Exception:
        utc = datetime.now(timezone.utc)
        return int(utc.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


# --------------------------------------------------------------------------
# Shared public-guild technology state (global, one row per tech group)
# --------------------------------------------------------------------------

def get_group_state(group_id: int) -> Optional[dict]:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT group_id, head_tech_id, state, progress, fake_tech_id "
        "FROM public_guild_technology_states WHERE group_id = $1",
        group_id,
    )
    if row is None:
        first = _group_first_tech().get(group_id)
        if first is None:
            return None
        # The shared (public) head is pinned to the group's terminal (max
        # level) tech. The client's denominator (GetMaxLevel) is the head's
        # level, so pinning it to max makes the card show "current/max" and
        # stays upgradable without re-login: the client only levels up the
        # displayed tech locally and never re-refreshes the shared head.
        head = _group_max_tech().get(group_id, first)
        store.execute(
            "INSERT INTO public_guild_technology_states "
            "(group_id, head_tech_id, state, progress, fake_tech_id) "
            "VALUES ($1, $2, 1, 0, $2)",
            group_id, head,
        )
        return {
            "group_id": group_id, "head_tech_id": head,
            "state": 1, "progress": 0, "fake_tech_id": head,
        }
    return {
        "group_id": row[0], "head_tech_id": row[1],
        "state": row[2], "progress": row[3], "fake_tech_id": row[4],
    }


def set_group_state(group_id: int, head_tech_id: int, state: int, progress: int, fake_tech_id: int):
    store = get_default_store()
    store.execute(
        "UPDATE public_guild_technology_states "
        "SET head_tech_id = $2, state = $3, progress = $4, fake_tech_id = $5 "
        "WHERE group_id = $1",
        group_id, head_tech_id, state, progress, fake_tech_id,
    )


def get_player_tech(commander_id: int, group_id: int) -> Optional[int]:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT tech_id FROM guild_user_technology_states "
        "WHERE commander_id = $1 AND tech_group = $2",
        commander_id, group_id,
    )
    return row[0] if row else None


def _record_player_tech(commander_id: int, group_id: int, tech_id: int):
    store = get_default_store()
    exists = store.fetchrow(
        "SELECT 1 FROM guild_user_technology_states "
        "WHERE commander_id = $1 AND tech_group = $2",
        commander_id, group_id,
    )
    if exists:
        store.execute(
            "UPDATE guild_user_technology_states SET tech_id = $3, updated_at = now() "
            "WHERE commander_id = $1 AND tech_group = $2",
            commander_id, group_id, tech_id,
        )
    else:
        store.execute(
            "INSERT INTO guild_user_technology_states "
            "(commander_id, tech_group, tech_id, updated_at) VALUES ($1, $2, $3, now())",
            commander_id, group_id, tech_id,
        )


def ensure_player_tech_states(commander_id: int) -> list:
    """Make sure every tech group has a player-progress row and return the
    current tech id per group ordered by group id (1..6)."""
    store = get_default_store()
    existing = store.fetch(
        "SELECT tech_group, tech_id FROM guild_user_technology_states "
        "WHERE commander_id = $1",
        commander_id,
    )
    have = {r[0]: r[1] for r in existing}
    out = []
    for g in sorted(_group_first_tech().keys()):
        first = _group_first_tech()[g]
        if g in have:
            out.append(have[g])
        else:
            _record_player_tech(commander_id, g, first)
            out.append(first)
    return out


# --------------------------------------------------------------------------
# Donate (Logistics) task list
# --------------------------------------------------------------------------

def _donate_task_count() -> int:
    d = fetch_config_entry_data(GUILDSET_CATEGORY, "contribution_task_num")
    if not isinstance(d, dict):
        return 3
    try:
        return int(d.get("key_value", 3))
    except Exception:
        return 3


def _generate_donate_tasks(commander_id: int, day_key: int, n: int, *seed_parts: int) -> list:
    """Pick `n` distinct offers from the contribution pool.

    The draw is seeded deterministically per (commander, day). Extra
    ``seed_parts`` (e.g. the commit ordinal) make each draw distinct, so every
    contribution re-rolls the whole Logistics offer set instead of repeating
    the day's first list.
    """
    cm = _contrib_map()
    pool = list(cm.keys())
    if not pool:
        return []
    rng = LockedRand(deterministic_seed(commander_id, day_key, 62031, *seed_parts))
    chosen = []
    while len(chosen) < n and pool:
        idx = rng.uint32_n(len(pool)) % len(pool)
        chosen.append(pool.pop(idx))
    return chosen


def get_or_create_user_info(commander_id: int) -> dict:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT commander_id, guild_id, donate_count, benefit_time, weekly_task_flag, "
        "extra_donate, extra_operation, donate_tasks, donate_day "
        "FROM guild_user_infos WHERE commander_id = $1",
        commander_id,
    )
    if row is None:
        store.execute(
            "INSERT INTO guild_user_infos (commander_id, guild_id, donate_count, benefit_time, "
            "weekly_task_flag, extra_donate, extra_operation, donate_tasks, donate_day) "
            "VALUES ($1, 0, 0, 0, 0, 0, 0, '[]', 0)",
            commander_id,
        )
        return {
            "commander_id": commander_id, "guild_id": 0, "donate_count": 0,
            "benefit_time": 0, "weekly_task_flag": 0, "extra_donate": 0,
            "extra_operation": 0, "donate_tasks": [], "donate_day": 0,
        }
    dt = row[7]
    if isinstance(dt, str):
        try:
            dt = json.loads(dt)
        except Exception:
            dt = []
    if not dt:
        dt = []
    return {
        "commander_id": row[0], "guild_id": row[1], "donate_count": row[2],
        "benefit_time": row[3], "weekly_task_flag": row[4], "extra_donate": row[5],
        "extra_operation": row[6], "donate_tasks": dt, "donate_day": row[8] or 0,
    }


def update_user_info(commander_id: int, donate_count=None, donate_tasks=None, donate_day=None):
    store = get_default_store()
    if donate_tasks is not None:
        store.execute(
            "UPDATE guild_user_infos SET donate_tasks = $2 WHERE commander_id = $1",
            commander_id, json.dumps(donate_tasks),
        )
    if donate_count is not None:
        store.execute(
            "UPDATE guild_user_infos SET donate_count = $2 WHERE commander_id = $1",
            commander_id, donate_count,
        )
    if donate_day is not None:
        store.execute(
            "UPDATE guild_user_infos SET donate_day = $2 WHERE commander_id = $1",
            commander_id, donate_day,
        )


def reset_donate_if_new_day(commander_id: int) -> dict:
    """Reset the public-guild donate state if a new region day has started.

    The donate (exchange) limit is 3 times per day. donate_count lives in
    guild_user_infos and is only ever incremented by commits, so without a
    day marker it would stay at 3 forever and the player would never get new
    exchanges. donate_day stores the region day key the current state belongs
    to; when it differs from today, zero the count and regenerate the task
    list. Returns the (possibly updated) info dict."""
    info = get_or_create_user_info(commander_id)
    today = _day_key()
    if info["donate_day"] == today:
        return info
    n = _donate_task_count()
    tasks = _generate_donate_tasks(commander_id, today, n)
    update_user_info(commander_id, donate_count=0, donate_tasks=tasks, donate_day=today)
    info["donate_count"] = 0
    info["donate_tasks"] = tasks
    info["donate_day"] = today
    return info


def ensure_donate_tasks(commander_id: int) -> list:
    info = reset_donate_if_new_day(commander_id)
    if info["donate_tasks"]:
        return info["donate_tasks"]
    n = _donate_task_count()
    tasks = _generate_donate_tasks(commander_id, _day_key(), n)
    update_user_info(commander_id, donate_tasks=tasks)
    return tasks


# --------------------------------------------------------------------------
# Public-guild technology response (SC_62101)
# --------------------------------------------------------------------------

def build_public_guild_tech_response() -> "protobuf.SC_62101":
    resp = protobuf.SC_62101()
    for g in sorted(_group_first_tech().keys()):
        st = get_group_state(g)
        if st is None:
            continue
        t = resp.technologys.add()
        t.id = st["head_tech_id"]
        t.state = st["state"]
        t.progress = st["progress"]
    return resp


# --------------------------------------------------------------------------
# Packet handlers
# --------------------------------------------------------------------------

async def handle_public_guild_upgrade_tech(buffer: bytes, client) -> tuple:
    req = protobuf.CS_62015()
    try:
        req.ParseFromString(buffer)
    except Exception:
        req = None
    response = protobuf.SC_62016(result=1)
    if req is None or getattr(client, "commander", None) is None:
        return await client.send_message(62016, response)

    commander_id = client.commander.commander_id
    m = _tech_map()
    d = m.get(req.id)
    if d is None:
        return await client.send_message(62016, response)

    group_id = d.get("group")
    next_tech = d.get("next_tech", 0)
    if not next_tech:
        return await client.send_message(62016, response)  # already max level

    ensure_player_tech_states(commander_id)
    player_tech = get_player_tech(commander_id, group_id)
    if player_tech is None:
        player_tech = req.id
    # The client sends the player's current (displayed) tech; only allow
    # upgrading exactly that one.
    if req.id != player_tech:
        return await client.send_message(62016, response)

    st = get_group_state(group_id)
    if st is None:
        return await client.send_message(62016, response)

    # The shared head stays pinned at the group's max-level tech (set in
    # get_group_state); only the player's own progress advances. This keeps
    # the client's denominator at the maximum level so the card remains
    # upgradable across many upgrades within a single session.
    head_new = st["head_tech_id"]

    # The player is always behind the shared head here, so no price rise.
    # The client (PublicGuildTechnology.GetConsume) ALWAYS charges
    # contribution_consume * contribution_multiple and gold_consume *
    # contribution_multiple -- it deducts both locally on purchase, so the
    # server must use the same formula or client and DB drift apart.
    multiple = float(d.get("contribution_multiple", 1) or 1)
    gold_cost = int(round(int(d.get("gold_consume", 0) or 0) * multiple))
    contrib_cost = int(round(int(d.get("contribution_consume", 0) or 0) * multiple))

    if gold_cost and not await has_enough_resource_async(commander_id, GOLD_RES, gold_cost):
        return await client.send_message(62016, response)
    if contrib_cost and not await has_enough_resource_async(commander_id, GUILD_COIN_RES, contrib_cost):
        return await client.send_message(62016, response)

    if gold_cost:
        await consume_resource_async(commander_id, GOLD_RES, gold_cost)
    if contrib_cost:
        await consume_resource_async(commander_id, GUILD_COIN_RES, contrib_cost)

    set_group_state(group_id, head_new, st["state"], 0, head_new)
    _record_player_tech(commander_id, group_id, next_tech)

    response.result = 0
    return await client.send_message(62016, response)


async def handle_public_guild_commit_donate(buffer: bytes, client) -> tuple:
    req = protobuf.CS_62002()
    try:
        req.ParseFromString(buffer)
    except Exception:
        req = None
    response = protobuf.SC_62003(result=1)
    if req is None or getattr(client, "commander", None) is None:
        return await client.send_message(62003, response)

    commander_id = client.commander.commander_id
    task_id = req.id
    cm = _contrib_map()
    task = cm.get(task_id)
    if task is None:
        return await client.send_message(62003, response)

    info = reset_donate_if_new_day(commander_id)
    max_cnt = _donate_task_count()
    if info["donate_count"] >= max_cnt:
        return await client.send_message(62003, response)
    dtype = task.get("type")
    res_id = task.get("type_id")
    amount = task.get("consume", 0) or 0

    if dtype == 1:
        if not await has_enough_resource_async(commander_id, res_id, amount):
            return await client.send_message(62003, response)
        await consume_resource_async(commander_id, res_id, amount)
    elif dtype == 2:
        if not has_enough_item(commander_id, res_id, amount):
            return await client.send_message(62003, response)
        consume_item(commander_id, res_id, amount)
    else:
        return await client.send_message(62003, response)

    award = task.get("award_contribution", 0) or 0
    if award:
        add_resource(commander_id, GUILD_COIN_RES, award)

    new_count = info["donate_count"] + 1
    # Original behavior: a successful contribution re-rolls the WHOLE offer
    # set, so each of the day's attempts is made against a fresh menu of
    # `contribution_task_num` offers (all three Logistics cards change).
    tasks = _generate_donate_tasks(commander_id, _day_key(), max_cnt, new_count)
    update_user_info(commander_id, donate_count=new_count, donate_tasks=tasks)

    # Advance "Contribute X times to your Guild Logistics" missions (task sub_type 402).
    try:
        from src.answer.task_handlers import emit_task_progress
        await emit_task_progress(client, GUILD_LOGISTICS_DONATE_EVENT, 0, 1)
    except Exception as e:
        log_event("Guild", "Donate", f"uid={commander_id} logistics task progress emit failed: {e}", LOG_LEVEL_ERROR)

    response.result = 0
    for t in tasks:
        response.donate_tasks.append(t)
    return await client.send_message(62003, response)


async def handle_public_guild_refresh_donate(_buffer: bytes, client) -> tuple:
    if getattr(client, "commander", None) is None:
        return 0, 62032, None
    commander_id = client.commander.commander_id
    day = _day_key()
    n = _donate_task_count()
    tasks = _generate_donate_tasks(commander_id, day, n)
    update_user_info(commander_id, donate_count=0, donate_tasks=tasks, donate_day=day)
    response = protobuf.SC_62031()
    for t in tasks:
        response.donate_tasks.append(t)
    return await client.send_message(62032, response)
