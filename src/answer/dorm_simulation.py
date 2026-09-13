import asyncio
import json
import random
from datetime import datetime, timezone
from typing import Optional


def load_dorm_level_template(level: int) -> Optional[dict]:
    if level == 0:
        level = 1
    from src.orm.config_entry import get_config_entry
    entry = get_config_entry("ShareCfg/dorm_data_template.json", str(level))
    if entry is None:
        return None
    raw = entry.data if hasattr(entry, "data") else entry
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        if raw.get("id", 0) == 0:
            raw["id"] = level
        return raw
    return None


# Client INDEX_TO_COMFORTABLE_TYPE (furniture.lua) maps furniture `type` (1..16)
# to a comfort group 1..7 used by dorm template `comfortable_count`.
_INDEX_TO_COMFORTABLE_TYPE = [
    1,  # WALLPAPER
    2,  # FURNITURE
    3,  # DECORATE
    4,  # FLOORPAPER
    5,  # MAT
    6,  # WALL
    7,  # COLLECTION
    2,  # STAGE -> FURNITURE
    2,  # ARCH -> FURNITURE
    6,  # WALL_MAT -> WALL
    2, 2, 2, 2, 2, 2,  # MOVEABLE..RANDOM_SLOT -> FURNITURE
]
_TYPE_FURNITURE = 2  # default group when type out of range

_DORM_2_FLOOR_COMFORTABLE_ADDITION = 20  # client Dorm.DORM_2_FLOOR_COMFORTABLE_ADDITION

# Wiki: with no supplies (food) the shipgirls still gain exp at a reduced rate
# (EXP per hour @ 0 supplies = EXP per hour * 0.25).
DORM_NO_SUPPLY_EXP_FACTOR = 0.25

# gameset dorm_*_pop_rant base: chance = rant / 10000 (project-wide chance
# convention, same base as ambush_ratio_extra / CHAPTER_CHANCE_BASE). Verified
# against official captures: 2 intimacy pops / 36 ship-pop-windows == 5.6% ~
# rant 500 = 5%; a 50% reading would have produced ~18 hits.
DORM_POP_RANT_BASE = 10000


async def _fetch_pop_chances() -> tuple[float, float]:
    rant_i = await _fetch_gameset_value("dorm_intimacy_pop_rant", 500)
    rant_m = await _fetch_gameset_value("dorm_dorm_pop_rant", 500)
    return rant_i / DORM_POP_RANT_BASE, rant_m / DORM_POP_RANT_BASE


def roll_pop_values(pop_count: int, chance_intimacy: float, chance_money: float,
                    intimacy_min: int, intimacy_max: int,
                    money_min: int, money_max: int) -> tuple[int, int]:
    """Roll one ship's dorm pop over `pop_count` elapsed dorm_pop_time windows.

    Each window is an independent trial at the gameset chance, so an overnight
    absence rolls more windows than a single 30-min poll; the reward is still
    ONE pending roll per ship (delivered values are SET, never accumulated).
    Intimacy and dorm money are independent (official SC_19010 carries
    (intimacy=2, dorm_icon=0): hearts without coins). Either side can be 0 --
    a (0, 0) result means no pending pop for this settlement.
    """
    if pop_count <= 0:
        return 0, 0
    p_intimacy = 1.0 - (1.0 - chance_intimacy) ** pop_count
    p_money = 1.0 - (1.0 - chance_money) ** pop_count
    intimacy = random.randint(intimacy_min, intimacy_max) if random.random() < p_intimacy else 0
    money = random.randint(money_min, money_max) if random.random() < p_money else 0
    return intimacy, money


async def _fetch_gameset_value( key: str, default: int = 0) -> int:
    from src.orm.config_entry import afetch_config_entry_data
    data = await afetch_config_entry_data('ShareCfg/gameset.json', key)
    if isinstance(data, dict):
        return int(data.get("key_value", default))
    return default


async def _fetch_commander_level(store, commander_id: int) -> int:
    row = await store.afetchrow(
        "SELECT level FROM commanders WHERE commander_id = $1", int(commander_id)
    )
    if row is None:
        return 1
    return int(row["level"] or 1)


async def _load_furniture_template( furniture_id: int) -> Optional[dict]:
    from src.orm.config_entry import afetch_config_entry_data
    data = await afetch_config_entry_data('ShareCfg/furniture_data_template.json', furniture_id)
    return data if isinstance(data, dict) else None


async def _compute_dorm_comfortable(store, commander_id: int, tpl: dict, floor_num: int) -> int:
    """Client Dorm:getComfortable() (newbackyard/dorm.lua)."""
    rows = await store.afetch(
        "SELECT furniture_id, count FROM commander_furnitures WHERE commander_id = $1",
        int(commander_id),
    )
    groups = {}
    # One batched template lookup for the whole furniture set: a per-row
    # config_entries roundtrip is an N+1 (537 rows -> ~0.8s through the async
    # pool) and made every dorm tick boundary crawl. ANY($1) expands to IN
    # (...) on SQLite via the dialect.
    furniture_ids = [int(r["furniture_id"]) for r in rows]
    cfg_by_id = {}
    if furniture_ids:
        from src.orm.config_entry import afetch_config_entries_map

        tpl_map = await afetch_config_entries_map(
            'ShareCfg/furniture_data_template.json',
            furniture_ids,
        )
        for key_str, cfg in tpl_map.items():
            if isinstance(cfg, dict):
                try:
                    cfg_by_id[int(key_str)] = cfg
                except (TypeError, ValueError):
                    continue
    for r in rows:
        cfg = cfg_by_id.get(int(r["furniture_id"]))
        if cfg is None:
            continue
        ftype = int(cfg.get("type", 0))
        if 1 <= ftype <= len(_INDEX_TO_COMFORTABLE_TYPE):
            ctype = _INDEX_TO_COMFORTABLE_TYPE[ftype - 1]
        else:
            ctype = _TYPE_FURNITURE
        comfortable = int(cfg.get("comfortable", 0))
        cnt = int(r["count"] or 1)
        groups.setdefault(ctype, []).extend([comfortable] * cnt)
    total = 0
    for pair in tpl.get("comfortable_count", []) or []:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        gtype = int(pair[0])
        maxn = int(pair[1])
        vals = sorted(groups.get(gtype, []) or [], reverse=True)[:maxn]
        total += sum(vals)
    total += int(tpl.get("comfortable", 0) or 0)
    if int(floor_num or 1) >= 2:
        total += _DORM_2_FLOOR_COMFORTABLE_ADDITION
    return total


async def _load_benefit_buff_config( buff_id: int) -> Optional[dict]:
    from src.orm.config_entry import afetch_config_entry_data
    data = await afetch_config_entry_data('ShareCfg/benefit_buff_template.json', buff_id)
    return data if isinstance(data, dict) else None


async def _fetch_dorm_exp_buff_entries(store, commander_id: int, after_ts: int) -> list:
    """Return list of (expires_at_unix, effect) for active dorm_exp benefit
    buffs whose expiry is after `after_ts` (so they were in effect during the
    settlement window). The expiry lets exp be segmented into buffed/unbuffed
    periods."""
    rows = await store.afetch(
        """SELECT b.buff_id, b.expires_at
           FROM commander_buffs b
           WHERE b.commander_id = $1 AND b.expires_at > $2""",
        int(commander_id),
        datetime.fromtimestamp(after_ts, timezone.utc),
    )
    out = []
    for row in rows:
        entry = await _load_benefit_buff_config(int(row["buff_id"]))
        if entry is None or entry.get("benefit_type") != "dorm_exp":
            continue
        from src.misc.safe_ts import safe_ts
        exp_ts = safe_ts(row["expires_at"])
        try:
            effect = float(entry.get("benefit_effect", 0) or 0)
        except (TypeError, ValueError):
            effect = 0.0
        out.append((exp_ts, effect))
    return out


def _segmented_dorm_exp_total(buff_entries: list, win_start: int, win_end: int,
                              tick_time: int, per_tick_exp_base: float) -> float:
    """Sum exp over the [win_start, win_end] window, splitting it at every buff
    expiry so buffed and unbuffed periods use their own factor."""
    if per_tick_exp_base <= 0 or tick_time <= 0 or win_end <= win_start:
        return 0.0
    boundaries = [win_start]
    for exp_ts, _ in buff_entries:
        if win_start < exp_ts <= win_end:
            boundaries.append(exp_ts)
    boundaries.append(win_end)
    boundaries = sorted(set(boundaries))
    total = 0.0
    for i in range(len(boundaries) - 1):
        seg_start, seg_end = boundaries[i], boundaries[i + 1]
        if seg_end <= seg_start:
            continue
        factor = 1.0
        for exp_ts, effect in buff_entries:
            if exp_ts > seg_start:
                factor += effect / 100.0
        seg_ticks = (seg_end - seg_start) / tick_time
        total += per_tick_exp_base * factor * seg_ticks
    return total


async def _recover_dorm_morale(store, commander_id: int, dorm_ships: list, window_seconds: int):
    """Recover morale (energy) for ships on either dorm floor over the elapsed
    window. Rates (wiki): 1F 40/hr (+10 married), 2F 50/hr (+10 married),
    cap 150. Advances state_info1 anchor so the generic login morale recovery
    does not double-count dorm time."""
    if window_seconds <= 0:
        return
    for ship in dorm_ships:
        floor = ship.get("floor", 1)
        married = int(ship.get("propose", 0) or 0) > 0
        if floor == 2:
            rate = 60.0 if married else 50.0
        else:
            rate = 50.0 if married else 40.0
        energy = int(ship.get("energy", 0) or 0)
        gained = int(rate * window_seconds / 3600.0)
        new_energy = energy + gained
        if new_energy > 150:
            new_energy = 150
        new_anchor = int(ship.get("state_info1", 0) or 0) + window_seconds
        await store.aexecute(
            """UPDATE owned_ships SET energy = $3, state_info1 = $4
               WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
            int(commander_id), int(ship["id"]), int(new_energy), int(new_anchor),
        )


async def tick_dorm_state(commander_id: int, now: int) -> Optional[dict]:
    from src.orm.commander_dorm_state import get_or_create_commander_dorm_state, save_commander_dorm_state
    from src.db.store import get_default_store

    store = get_default_store()
    # The sync-SA helpers block the event loop while they wait for SQLite's
    # single writer lock (a long write transaction — data import, admin op,
    # test-suite load — can hold it for seconds). Run them in a worker thread
    # so the polled CS_19026 path cannot freeze the whole server.
    state_orm = await asyncio.to_thread(get_or_create_commander_dorm_state, commander_id)
    state = {c.name: getattr(state_orm, c.name) for c in state_orm.__table__.columns}
    tpl = load_dorm_level_template(state.get("level", 1))
    if tpl is None or tpl.get("time", 0) == 0:
        return {"pop_list": [], "exp_gained": 0, "food_consume": 0, "next_timestamp": 0}
    rows = await store.afetch(
        """SELECT id, ship_id, level, exp, surplus_exp, max_level, intimacy,
                  state, state_info1, state_info2, state_info3, state_info4,
                  energy, propose
          FROM owned_ships
          WHERE owner_id = $1 AND deleted_at IS NULL AND (state = 5 OR state = 2)""",
        int(commander_id),
    )
    dorm_ships = []
    for row in rows:
        ship = dict(row)
        ship["id"] = int(ship["id"])
        ship["ship_id"] = int(ship["ship_id"])
        # floor 1 = training (state 5), floor 2 = rest (state 2)
        ship["floor"] = 1 if int(ship.get("state", 0)) == 5 else 2
        dorm_ships.append(ship)

    # Current pending pop values (si3 intimacy / si4 dorm money) already in
    # the DB. Used on early-return branches so SC_19010 always carries them:
    # the client's red-dot/collect buttons refresh ONLY from SC_19001 and the
    # 30-min CS_19009 poll, never on dorm entry, so pending values must be
    # delivered even when no new pop/exp window has completed.
    def _pending_pop_list():
        pending = []
        for ship in dorm_ships:
            si3 = int(ship.get("state_info3", 0) or 0)
            si4 = int(ship.get("state_info4", 0) or 0)
            if si3 or si4:
                pending.append({"id": ship["id"], "intimacy": si3, "dorm_icon": si4})
        return pending

    if not dorm_ships:
        state["next_timestamp"] = 0
        state["updated_at_unix_timestamp"] = now
        await asyncio.to_thread(save_commander_dorm_state, state)
        return {"pop_list": [], "exp_gained": 0, "food_consume": 0, "next_timestamp": 0}
    last = state.get("updated_at_unix_timestamp", 0)
    if last == 0:
        state["updated_at_unix_timestamp"] = now
        await asyncio.to_thread(save_commander_dorm_state, state)
        return {"pop_list": [], "exp_gained": 0, "food_consume": 0, "next_timestamp": 0}
    if now <= last:
        return {
            "pop_list": _pending_pop_list(), "exp_gained": 0, "food_consume": 0,
            "next_timestamp": state.get("next_timestamp", 0),
        }
    elapsed = now - last
    tick_time = tpl.get("time", 0)
    ticks = elapsed // tick_time
    if ticks == 0:
        # Keep last tick time untouched: partial seconds must accumulate
        # toward the next full tick instead of being discarded by resetting
        # updated_at_unix_timestamp to now.
        return {
            "pop_list": _pending_pop_list(), "exp_gained": 0, "food_consume": 0,
            "next_timestamp": state.get("next_timestamp", 0),
        }

    orig_ticks = ticks
    training_ships = [s for s in dorm_ships if s.get("floor") == 1]
    training_count = len(training_ships)
    n_idx = max(1, min(training_count, 6))
    exp_ratio = await _fetch_gameset_value("dorm_exp_ratio_by_%d" % n_idx, 100)
    food_ratio = await _fetch_gameset_value("dorm_food_ratio_by_%d" % n_idx, 100)
    exp_base = await _fetch_gameset_value("dorm_exp_base", 1)
    comfort_degree = await _fetch_gameset_value("dorm_exp_ratio_comfort_degree", 100)

    comfortable = await _compute_dorm_comfortable(store, commander_id, tpl, state.get("floor_num", 1))
    commander_level = await _fetch_commander_level(store, commander_id)

    consume = tpl.get("consume", 0)
    per_tick_food = (food_ratio / 100.0) * consume
    # Food is drained only by training (1F) ships; the rest floor does not
    # consume food per the dorm wiki.
    food_consume = 0
    exp_gained = 0
    per_ship_exp = 0
    if training_count > 0:
        # Client GetBaseExp (backyardshipcard.lua):
        #   exp_ratio/100 * (dorm_exp_base + tpl.exp * comfort/(comfort + comfort_degree))
        #   * buffFactor * (1 + 0.05 * commander.level)
        #   -> EXP/hr = 240*Modifier*(1+CL/20)*(1+Comfort/(Comfort+100))*(1+FoodBuff)
        # buffFactor is segmented across the window so a dorm_exp buff that
        # expires mid-window only buffs the portion before expiry.
        base_inside = exp_base + (tpl.get("exp", 0) * comfortable / (comfortable + comfort_degree))
        per_tick_exp_base = (exp_ratio / 100.0) * base_inside * (1 + 0.05 * commander_level)
        buff_entries = await _fetch_dorm_exp_buff_entries(store, commander_id, last)

        # Supplies (food) gate the FULL exp rate; once food is exhausted the
        # ships keep training at the reduced DORM_NO_SUPPLY_EXP_FACTOR rate
        # (wiki: EXP per hour @ 0 supplies = EXP per hour * 0.25) without
        # consuming food. Food drains continuously: the last partial tick
        # consumes whatever remains, so food reaches exactly 0 instead of
        # stranding a sub-tick remainder (e.g. 102000 % 18 = 12) forever.
        food_ticks = ticks
        food_now = state.get("food", 0)
        if per_tick_food > 0:
            max_ticks_by_food = food_now / per_tick_food
            food_ticks = min(ticks, max_ticks_by_food)

        food_window_end = last + food_ticks * tick_time
        exp_total = _segmented_dorm_exp_total(buff_entries, last, food_window_end, tick_time, per_tick_exp_base)
        if food_ticks < ticks:
            no_supply_window_end = last + ticks * tick_time
            exp_total += (
                _segmented_dorm_exp_total(
                    buff_entries, food_window_end, no_supply_window_end, tick_time, per_tick_exp_base
                )
                * DORM_NO_SUPPLY_EXP_FACTOR
            )

        food_consume = int(per_tick_food * food_ticks)
        if food_ticks < ticks:
            # Food ran out inside this window: drain it to exactly 0 so
            # float rounding cannot strand a sub-tick remainder.
            food_consume = food_now
        state["food"] = food_now - food_consume
        state["load_food"] = state.get("load_food", 0) + food_consume

        # Accumulate fractional exp across ticks so int() truncation does not
        # lose ~0.5 exp per tick (which compounds to ~19% per hour).
        exp_frac = float(state.get("exp_fraction", 0.0) or 0.0) + exp_total
        per_ship_exp = int(exp_frac)
        state["exp_fraction"] = exp_frac - per_ship_exp
        exp_gained = per_ship_exp * training_count
        state["load_exp"] = state.get("load_exp", 0) + exp_gained

    state["load_time"] = now
    # Anchor advances by the full elapsed window; even with no supplies the
    # ships keep training (at the reduced rate), so the whole window is
    # settled now and the remainder is not deferred to a later poll.
    state["updated_at_unix_timestamp"] = last + ticks * tick_time
    if training_count > 0:
        state["next_timestamp"] = state["updated_at_unix_timestamp"] + tick_time
    else:
        state["next_timestamp"] = 0

    # Morale recovers for ships on both floors over the whole elapsed window
    # (food running out pauses exp, not morale).
    await _recover_dorm_morale(store, commander_id, dorm_ships, orig_ticks * tick_time)

    # Dorm "pop" events award a small random amount per pop, not per tick, and
    # are CHANCE-based (gameset dorm_*_pop_rant = 500/10000 = 5% per window per
    # side, rolled independently -- see roll_pop_values). pop_time_accum
    # carries partial windows across tick calls so the cadence stays aligned
    # to dorm_pop_time.
    dorm_pop_time = await _fetch_gameset_value("dorm_pop_time", 1800)
    intimacy_pop_min = await _fetch_gameset_value("dorm_intimacy_pop_min", 1)
    intimacy_pop_max = await _fetch_gameset_value("dorm_intimacy_pop_max", 2)
    dorm_pop_min = await _fetch_gameset_value("dorm_dorm_pop_min", 1)
    dorm_pop_max = await _fetch_gameset_value("dorm_dorm_pop_max", 3)
    if dorm_pop_time <= 0:
        dorm_pop_time = 1800
    if intimacy_pop_max < intimacy_pop_min:
        intimacy_pop_max = intimacy_pop_min
    if dorm_pop_max < dorm_pop_min:
        dorm_pop_max = dorm_pop_min

    sim_seconds = ticks * tick_time
    pop_accum = int(state.get("pop_time_accum", 0) or 0) + sim_seconds
    pop_count = 0
    if pop_accum >= dorm_pop_time:
        pop_count = pop_accum // dorm_pop_time
        pop_accum = pop_accum % dorm_pop_time
    state["pop_time_accum"] = pop_accum

    # Per pop window a ship gets ONE CHANCE (not a guaranteed roll): gameset
    # dorm_intimacy_pop_rant / dorm_dorm_pop_rant (both 500) out of 10000 = 5%
    # each, and intimacy / dorm money roll INDEPENDENTLY. Verified against
    # official captures: 12 CS_19009 polls with 3 dorm ships -> 2 intimacy pops
    # (one reported as (2, 0): hearts without coins), 0 money pops.
    chance_intimacy, chance_money = await _fetch_pop_chances()

    pop_list = []
    for ship in dorm_ships:
        si2 = int(ship.get("state_info2", 0))
        if ship.get("floor") == 1:
            si2 += per_ship_exp
        pending_si3 = int(ship.get("state_info3", 0))
        pending_si4 = int(ship.get("state_info4", 0))
        if pop_count > 0 and not (pending_si3 or pending_si4):
            # Only roll a NEW pop when the previous one has been delivered
            # (pending zeroed). Overwriting an undelivered pending would lose
            # it -- the client only collects what SC_19010/SC_19001 reports.
            si3, si4 = roll_pop_values(
                pop_count, chance_intimacy, chance_money,
                intimacy_pop_min, intimacy_pop_max, dorm_pop_min, dorm_pop_max,
            )
        else:
            si3 = pending_si3
            si4 = pending_si4
        await store.aexecute(
            """UPDATE owned_ships
             SET state_info2 = $3, state_info3 = $4, state_info4 = $5
             WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
            int(commander_id), int(ship["id"]), int(si2), int(si3), int(si4),
        )
        pop_list.append({
            "id": ship["id"],
            "intimacy": si3,
            "dorm_icon": si4,
        })
    await asyncio.to_thread(save_commander_dorm_state, state)
    return {
        "pop_list": pop_list,
        "exp_gained": exp_gained,
        "food_consume": food_consume,
        "next_timestamp": state["next_timestamp"],
        "per_ship_exp": per_ship_exp,
    }


async def settle_dorm_pops_at_login(commander_id: int, now: int) -> list:
    """Roll pending dorm pop events (hearts/coins) without settling exp/food.

    Used by BOTH the login path (before SC_19001 is built, so the Backyard red
    dot and per-ship collect bubbles are already present) and the CS_19009
    30-min poll. Exp/food settlement must stay exclusive to CS_19026
    (handle_get_ship_exp_for_dorm_training): official SC_19010 carries ONLY
    pop_list, so anything settled here would never reach the client until the
    next dorm entry -- food would vanish silently and accumulated exp would
    pair with a wrong "snacks used" number in the "while you were away"
    popup.

    load_time / updated_at_unix_timestamp / food / exp are intentionally left
    untouched: the CS_19026 settlement must still see the full offline window
    so the popup shows the real elapsed time and food. The pop anchor
    (pop_time_accum) advances by the same elapsed wall-clock, and pending pops
    gate re-rolls, so the next real tick cannot double-roll.

    Returns the pop entries for every dorm ship ([{id, intimacy, dorm_icon}]
    -- current pending values, newly rolled or previously pending), the same
    shape tick_dorm_state's "pop_list" uses.
    """
    from src.orm.commander_dorm_state import get_or_create_commander_dorm_state, save_commander_dorm_state
    from src.db.store import get_default_store

    store = get_default_store()
    state_orm = await asyncio.to_thread(get_or_create_commander_dorm_state, commander_id)
    state = {c.name: getattr(state_orm, c.name) for c in state_orm.__table__.columns}

    dorm_pop_time = await _fetch_gameset_value("dorm_pop_time", 1800)
    intimacy_pop_min = await _fetch_gameset_value("dorm_intimacy_pop_min", 1)
    intimacy_pop_max = await _fetch_gameset_value("dorm_intimacy_pop_max", 2)
    dorm_pop_min = await _fetch_gameset_value("dorm_dorm_pop_min", 1)
    dorm_pop_max = await _fetch_gameset_value("dorm_dorm_pop_max", 3)
    if dorm_pop_time <= 0:
        dorm_pop_time = 1800
    if intimacy_pop_max < intimacy_pop_min:
        intimacy_pop_max = intimacy_pop_min
    if dorm_pop_max < dorm_pop_min:
        dorm_pop_max = dorm_pop_min

    rows = await store.afetch(
        """SELECT id, state_info3, state_info4
           FROM owned_ships
           WHERE owner_id = $1 AND deleted_at IS NULL AND (state = 5 OR state = 2)""",
        int(commander_id),
    )

    def _pending_entry(ship: dict) -> dict:
        return {
            "id": int(ship["id"]),
            "intimacy": int(ship.get("state_info3", 0) or 0),
            "dorm_icon": int(ship.get("state_info4", 0) or 0),
        }

    last = int(state.get("updated_at_unix_timestamp", 0) or 0)
    elapsed = int(now) - last if last > 0 else 0
    if last <= 0 or elapsed <= 0:
        # No elapsed window (fresh state / same-second poll): still report the
        # current pending values so the client's collect buttons stay alive.
        return [e for e in map(_pending_entry, map(dict, rows)) if e["intimacy"] or e["dorm_icon"]]

    pop_accum = int(state.get("pop_time_accum", 0) or 0) + elapsed
    if pop_accum < dorm_pop_time:
        return [e for e in map(_pending_entry, map(dict, rows)) if e["intimacy"] or e["dorm_icon"]]
    state["pop_time_accum"] = pop_accum % dorm_pop_time

    # Same chance-based roll as tick_dorm_state (gameset dorm_*_pop_rant);
    # each elapsed pop window is an independent trial, so an offline night
    # rolls more windows than a single 30-min poll.
    chance_intimacy, chance_money = await _fetch_pop_chances()
    pop_count = pop_accum // dorm_pop_time

    pop_entries = []
    for row in rows:
        ship = dict(row)
        entry = _pending_entry(ship)
        if entry["intimacy"] or entry["dorm_icon"]:
            # Undelivered pending: keep it -- the client only collects what
            # SC_19001/SC_19010 reports, overwriting would lose it.
            pop_entries.append(entry)
            continue
        entry["intimacy"], entry["dorm_icon"] = roll_pop_values(
            pop_count, chance_intimacy, chance_money,
            intimacy_pop_min, intimacy_pop_max, dorm_pop_min, dorm_pop_max,
        )
        if entry["intimacy"] or entry["dorm_icon"]:
            await store.aexecute(
                """UPDATE owned_ships SET state_info3 = $3, state_info4 = $4
                   WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
                int(commander_id), entry["id"], entry["intimacy"], entry["dorm_icon"],
            )
        pop_entries.append(entry)
    await asyncio.to_thread(save_commander_dorm_state, state)
    return pop_entries


async def tick_dorm_and_push(client) -> Optional[Exception]:
    import time
    try:
        res = await tick_dorm_state(client.commander.commander_id, int(time.time()))
        if res and res.get("pop_list"):
            from src.protobuf import protobuf
            msg = protobuf.SC_19010()
            for entry in res["pop_list"]:
                pop = msg.pop_list.add()
                pop.id = entry["id"]
                pop.intimacy = entry["intimacy"]
                pop.dorm_icon = entry["dorm_icon"]
            asyncio.create_task(client.send_message(19010, msg))
    except Exception as e:
        return e
    return None


async def save_dorm_owned_ship(commander_id: int, ship_id: int, ship: dict):
    from src.db.store import get_default_store

    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        """UPDATE owned_ships SET level = $3, exp = $4, surplus_exp = $5, intimacy = $6,
                  state = $7, state_info1 = $8, state_info2 = $9, state_info3 = $10, state_info4 = $11
         WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
        int(commander_id), int(ship_id),
        int(ship.get("level", 0)), int(ship.get("exp", 0)),
        int(ship.get("surplus_exp", 0)), int(ship.get("intimacy", 0)),
        int(ship.get("state", 0)), int(ship.get("state_info1", 0)),
        int(ship.get("state_info2", 0)), int(ship.get("state_info3", 0)),
        int(ship.get("state_info4", 0)),
    )
