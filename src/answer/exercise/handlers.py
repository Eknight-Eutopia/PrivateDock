"""Handlers for the Military Exercise (PvP / Mock Battles) feature.

Packet map:
  18001 -> 18002  get rivals + own season info
  18003 -> 18004 + 18005  replace rivals (New Opponents)
  18006 -> 18007  power rank list
  18008 -> 18009  update defense fleet
"""

from __future__ import annotations

import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

from .helpers import (
    ensure_exercise_state,
    build_exercise_rival_target_list,
    build_exercise_season_push_update,
    load_exercise_fleet_ids,
    owns_all_ships,
    tier_index_for_score,
    empty_display,
    EXERCISE_REFRESHES_PER_DAY,
)


def handle_exercise_enemies(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_18001()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 18002, e

    commander_id = client.commander.commander_id
    state = ensure_exercise_state(commander_id)

    vanguard_ids, main_ids = load_exercise_fleet_ids(commander_id)

    response = protobuf.SC_18002()
    response.score = state.score
    response.rank = tier_index_for_score(state.score)
    response.fight_count = state.fight_count
    response.fight_count_reset_time = state.next_recover_time
    response.flash_target_count = state.refreshes_today
    response.vanguard_ship_id_list.extend(vanguard_ids)
    response.main_ship_id_list.extend(main_ids)
    targets = build_exercise_rival_target_list(commander_id, state)
    response.target_list.extend(targets)

    asyncio.create_task(client.send_message(18002, response))
    return 0, 18002, None


def handle_exercise_replace_rivals(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_18003()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 18004, e

    commander_id = client.commander.commander_id
    state = ensure_exercise_state(commander_id)

    response = protobuf.SC_18004()
    if state.refreshes_today <= 0:
        response.result = 1
        asyncio.create_task(client.send_message(18004, response))
        return 0, 18004, None

    state.refreshes_today -= 1
    from src.orm.exercise_state import upsert_exercise_state_sync
    upsert_exercise_state_sync(state)

    refresh_count = max(0, EXERCISE_REFRESHES_PER_DAY - state.refreshes_today)
    targets = build_exercise_rival_target_list(
        commander_id, state, refresh_count=refresh_count
    )
    response.result = 0
    response.target_list.extend(targets)

    # also push a season update so the client refreshes score/rank/rivals
    season_push = build_exercise_season_push_update(
        commander_id, state, refresh_count=refresh_count
    )
    asyncio.create_task(client.send_message(18004, response))
    asyncio.create_task(client.send_message(18005, season_push))
    return 0, 18004, None


def handle_exercise_power_rank_list(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_18006()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 18007, e

    commander_id = client.commander.commander_id
    state = ensure_exercise_state(commander_id)

    response = protobuf.SC_18007()
    # Rank list is leaderboard-style; we surface a few synthetic entries with
    # the player themselves near their own score. Client only renders names.
    for i in range(1, 11):
        entry = protobuf.ARENARANK()
        entry.id = i
        entry.name = f"Commander {i}"
        entry.score = max(0, state.score - (10 - i) * 10)
        entry.level = 1
        entry.display.CopyFrom(empty_display())
        response.arena_rank_lsit.append(entry)
    # ensure the player is present
    me = protobuf.ARENARANK()
    me.id = commander_id
    me.name = client.commander.name or "You"
    me.score = state.score
    me.level = client.commander.level
    me.display.CopyFrom(empty_display())
    response.arena_rank_lsit.append(me)

    asyncio.create_task(client.send_message(18007, response))
    return 0, 18007, None


def handle_update_exercise_fleet(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_18008()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 18009, e

    commander_id = client.commander.commander_id
    vanguard = list(payload.vanguard_ship_id_list)
    main = list(payload.main_ship_id_list)

    if not owns_all_ships(commander_id, vanguard) or not owns_all_ships(commander_id, main):
        response = protobuf.SC_18009()
        response.result = 1
        asyncio.create_task(client.send_message(18009, response))
        return 0, 18009, None

    from src.orm.exercise_fleet import upsert_exercise_fleet
    upsert_exercise_fleet(commander_id, vanguard, main)

    response = protobuf.SC_18009()
    response.result = 0
    asyncio.create_task(client.send_message(18009, response))
    return 0, 18009, None
