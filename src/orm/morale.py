from __future__ import annotations

from src.db.store import get_default_store
from src.orm.active_event import get_active_event_count_sync

MORALE_TICK_SECONDS = 360
MORALE_BASE_CAP = 119
MORALE_DORM_CAP = 150
MORALE_ONSEN_CAP = 150
# Wiki rates (MORALE_TICK_SECONDS = 360s, so per-hour = gain * 10):
#   not in dorm: 20/hr (2/tick) unmarried, 30/hr (3/tick) married
#   dorm floors: handled separately in the dorm tick (40/50 per hr 1F, 50/60 2F)
#   Marriage raises the recovery RATE, not the morale cap (default max 119,
#   dorm max 150 for both married and unmarried).
MORALE_BASE_TICK_GAIN = 2
MORALE_MARRIAGE_TICK_GAIN = 1
MORALE_ONSEN_EXTRA_TICK_GAIN = 1

SHIP_STATE_DORM_REST = 2
SHIP_STATE_DORM_TRAINING = 5
SHIP_STATE_ONSEN = 6


def get_active_event_count(commander_id: int) -> int:
    return get_active_event_count_sync(commander_id)


def is_dorm_ship_state(state: int) -> bool:
    return state == SHIP_STATE_DORM_REST or state == SHIP_STATE_DORM_TRAINING


def morale_recovery_profile(state: int, proposed: bool, onsen_enabled: bool) -> tuple[int, int]:
    cap = MORALE_BASE_CAP
    gain = MORALE_BASE_TICK_GAIN

    if is_dorm_ship_state(state):
        cap = MORALE_DORM_CAP
    if proposed:
        # Wiki: a married (oathed) ship recovers +10 morale/hr faster; the
        # marriage does not raise the morale cap.
        gain += MORALE_MARRIAGE_TICK_GAIN
    if onsen_enabled and state == SHIP_STATE_ONSEN:
        cap = MORALE_ONSEN_CAP
        gain += MORALE_ONSEN_EXTRA_TICK_GAIN

    return gain, cap


def apply_commander_morale_recovery(commander_id: int, now_unix: int) -> int:
    if now_unix == 0:
        return 0

    active_event_count = get_active_event_count_sync(commander_id)
    onsen_enabled = active_event_count > 0

    store = get_default_store()
    try:
        rows = store.fetch(
            "SELECT id, energy, state, state_info1, propose FROM owned_ships WHERE owner_id = $1 AND deleted_at IS NULL",
            commander_id,
        )
    except Exception:
        return 0

    next_tick = 0
    for row in rows:
        ship_id = row[0]
        energy = row[1]
        state = row[2]
        anchor = row[3]
        propose = row[4]

        # Dorm ships (training/rest) recover morale via the dorm tick at the
        # dorm-specific rates; skip here to avoid double-counting and the wrong
        # generic dorm gain.
        if is_dorm_ship_state(state):
            continue

        if anchor == 0:
            anchor = now_unix

        updated_energy = energy
        updated_anchor = anchor
        ticks = 0
        if now_unix > anchor:
            ticks = (now_unix - anchor) // MORALE_TICK_SECONDS
            if ticks > 0:
                updated_anchor = anchor + ticks * MORALE_TICK_SECONDS
                gain, cap = morale_recovery_profile(state, propose, onsen_enabled)
                if updated_energy < cap and gain > 0:
                    max_gain = cap - updated_energy
                    total_gain = ticks * gain
                    if total_gain > max_gain:
                        total_gain = max_gain
                    updated_energy += total_gain

        if updated_energy != energy or updated_anchor != anchor:
            store.execute(
                "UPDATE owned_ships SET energy = $1, state_info1 = $2 WHERE owner_id = $3 AND id = $4 AND deleted_at IS NULL",
                updated_energy, updated_anchor, commander_id, ship_id,
            )

        _, cap = morale_recovery_profile(state, propose, onsen_enabled)
        if updated_energy < cap:
            candidate = updated_anchor + MORALE_TICK_SECONDS
            if next_tick == 0 or candidate < next_tick:
                next_tick = candidate

    return next_tick
