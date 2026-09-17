"""Secretary affinity tick.

The ship set as the MAIN secretary (leftmost slot, ``secretary_position = 0``)
gains 1 affinity point every 300-320 minutes (randomized per tick). Gain stops
at 90 affinity; during romance events gain over 90 is possible (the rate may
be lower than normal) -- see ``_romance_cap_units``.

Storage: per-commander anchor columns on ``commanders``:
  - ``secretary_affinity_last_ts``      (timestamptz) moment of the last applied tick
  - ``secretary_affinity_interval_min`` (integer)    minutes until the NEXT tick

Client delivery (verified against the EN client Lua):
  - Login catch-up runs in ``join_server`` right after ``Commander.load()``, so
    the fresh intimacy flows out with the normal login dock sync
    (SC_12001 / SC_12010) -- no extra packet needed.
  - While online, the background loop (``secretary_affinity_loop``, started
    from ``src/entrypoint/server.py``) applies due ticks and pushes
    ``SC_12019{intimacy}``: ``BayProxy:on(12019)`` sets likability on the main
    secretary ship (``player.character``) and refreshes the dock VO.
  - The "random secretary" display mode is purely client-side rotation
    (``Player.GetRandomFlagShip`` / ``SettingsProxy.rotateCurrentSecretaryIndex``);
    the server always ticks the ORIGINAL leftmost ship, matching the official
    behavior.

Scale: 1 client-visible affinity point == 100 DB intimacy units (same scale as
battle intimacy, see ``battle_session._compute_intimacy_delta``).
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from src.logger.logger import log_event, LOG_LEVEL_INFO, LOG_LEVEL_ERROR

# 1 client affinity point == 100 DB intimacy units
INTIMACY_PER_AFFINITY_POINT = 100
# Secretary affinity gain stops at 90 affinity unless a romance event raises the cap
DEFAULT_CAP_AFFINITY = 90
# Official gain window: one point every 300-320 minutes (randomized per tick)
SECRETARY_TICK_MIN_MINUTES = 300
SECRETARY_TICK_MAX_MINUTES = 320
_DEFAULT_INTERVAL_MIN = (
    SECRETARY_TICK_MIN_MINUTES + SECRETARY_TICK_MAX_MINUTES
) // 2


@dataclass
class SecretaryAffinityComputation:
    """Pure result of one :func:`compute_secretary_tick` run."""
    granted_units: int          # DB intimacy units granted this tick (0 when only re-anchoring)
    new_intimacy: int           # intimacy value as computed (may be stale if a battle raced)
    new_last_ts: datetime       # anchor to persist for the next tick
    new_interval_min: int       # minutes until the NEXT tick (re-rolled after each tick)
    capped: bool                # True when the cap was reached and the anchor was pinned


@dataclass
class SecretaryAffinityGrant:
    """Applied grant returned by :func:`tick_secretary_affinity`."""
    owned_id: int
    ship_id: int
    granted_units: int
    intimacy: int               # fresh DB value after the grant


def _romance_cap_units() -> int:
    """Secretary affinity cap in DB intimacy units.

    Hook for romance events: during those events gain over 90 affinity is
    possible (the original rate may be lower than normal). No EN romance-event
    config is wired yet, so the default cap (90 affinity = 9000 units) applies.
    Consult the active activity configs here when one is added.
    """
    return DEFAULT_CAP_AFFINITY * INTIMACY_PER_AFFINITY_POINT


def _roll_interval() -> int:
    return random.randint(SECRETARY_TICK_MIN_MINUTES, SECRETARY_TICK_MAX_MINUTES)


def compute_secretary_tick(
    last_ts: datetime,
    interval_min: int,
    intimacy: int,
    now: datetime,
    cap_units: int,
    roll: Optional[Callable[[], int]] = None,
) -> Optional[SecretaryAffinityComputation]:
    """Pure tick math; returns None when there is nothing to persist.

    ``roll`` lets tests pin the per-tick interval (production uses a random
    300-320 minute roll per tick). The anchor advances by exactly the granted
    intervals so fractional elapsed time is never lost, and while the ship sits
    at the cap the anchor is pinned to ``now`` so no "debt" accrues.
    """
    if interval_min is None or interval_min <= 0:
        interval_min = _DEFAULT_INTERVAL_MIN
    # Text()-level reads on SQLite hand back timestamptz as TEXT (the SA
    # sqlite engine runs without detect_types); asyncpg returns tz-aware
    # datetimes. Normalize both.
    if isinstance(last_ts, str):
        from src.db.sqlite_types import _convert_timestamp

        parsed = _convert_timestamp(last_ts)
        if parsed is None:
            return None
        last_ts = parsed
    if last_ts.tzinfo is None:  # defensive: asyncpg returns tz-aware datetimes
        last_ts = last_ts.replace(tzinfo=timezone.utc)

    remaining_min = (now - last_ts).total_seconds() / 60.0
    if remaining_min < 0:
        remaining_min = 0.0  # clock went backwards; re-anchor on the next interval

    granted = 0
    current = int(intimacy or 0)
    anchor = last_ts
    interval = interval_min
    while remaining_min >= interval and current < cap_units:
        step = min(INTIMACY_PER_AFFINITY_POINT, cap_units - current)
        current += step
        granted += step
        anchor = anchor + timedelta(minutes=interval)
        remaining_min -= interval
        interval = roll() if roll is not None else _roll_interval()

    capped = current >= cap_units
    if capped and (granted > 0 or remaining_min >= interval):
        # Gain has stopped: pin the anchor to now so no "debt" accrues while
        # the cap is in effect (and no burst appears if a romance event later
        # raises the cap). Re-pinning happens at most once per interval.
        anchor = now
        remaining_min = 0.0

    if granted == 0 and anchor == last_ts and interval == interval_min:
        return None
    return SecretaryAffinityComputation(
        granted_units=granted,
        new_intimacy=current,
        new_last_ts=anchor,
        new_interval_min=interval,
        capped=capped,
    )

async def tick_secretary_affinity(
    commander_id: int,
    client=None,
) -> Optional[SecretaryAffinityGrant]:
    """Apply all due secretary-affinity ticks for ``commander_id``.

    Grants 1 affinity point (100 DB units) per elapsed 300-320 minute interval
    to the ship in the LEFTMOST secretary slot, capped (see
    ``_romance_cap_units``). Keeps the live commander's in-memory dock map in
    sync when ``client`` is given. Returns the applied grant, or None when
    nothing was due / no secretary is set.
    """
    from src.db.store import get_default_store

    store = get_default_store()
    if store is None:
        return None

    now = datetime.now(timezone.utc)
    state = await store.afetchrow(
        "SELECT secretary_affinity_last_ts, secretary_affinity_interval_min "
        "FROM commanders WHERE commander_id = $1",
        commander_id,
    )
    if state is None:
        return None

    last_ts = state["secretary_affinity_last_ts"]
    if last_ts is None:
        # First run (e.g. a commander created before the migration): anchor
        # the tick clock without granting anything (no retroactive burst).
        await store.aexecute(
            "UPDATE commanders SET secretary_affinity_last_ts = $2, "
            "secretary_affinity_interval_min = $3 WHERE commander_id = $1",
            commander_id, now, _roll_interval(),
        )
        return None

    ship = await store.afetchrow(
        "SELECT id, ship_id, intimacy FROM owned_ships "
        "WHERE owner_id = $1 AND deleted_at IS NULL AND is_secretary "
        # PG-specific: COALESCE ordering, leftmost slot first
        "ORDER BY COALESCE(secretary_position, 999), id LIMIT 1",
        commander_id,
    )
    if ship is None:
        return None  # no (main) secretary set -- nothing accrues

    cap_units = _romance_cap_units()
    computation = compute_secretary_tick(
        last_ts,
        state["secretary_affinity_interval_min"],
        int(ship["intimacy"] or 0),
        now,
        cap_units,
    )
    if computation is None:
        return None

    # Atomic capped grant: LEAST(intimacy + granted, cap) keeps a
    # concurrent battle-intimacy write safe. -- PG-specific
    await store.aexecute(
        "UPDATE owned_ships SET intimacy = LEAST(intimacy + $2, $3) WHERE id = $1",
        ship["id"], computation.granted_units, cap_units,
    )
    await store.aexecute(
        "UPDATE commanders SET secretary_affinity_last_ts = $2, "
        "secretary_affinity_interval_min = $3 WHERE commander_id = $1",
        commander_id, computation.new_last_ts, computation.new_interval_min,
    )

    # Re-read so the push carries the value that actually landed (a battle
    # settlement may have added intimacy concurrently).
    fresh = await store.afetchval(
        "SELECT intimacy FROM owned_ships WHERE id = $1", ship["id"]
    )
    new_intimacy = int(fresh if fresh is not None else computation.new_intimacy)

    # Keep the live commander's in-memory dock map in sync (same pattern as
    # battle_session._apply_battle_ship_updates).
    if client is not None:
        mapping = getattr(getattr(client, "commander", None), "owned_ships_map", None) or {}
        owned = mapping.get(ship["id"])
        if owned is not None:
            owned["intimacy"] = min(
                cap_units,
                int(owned.get("intimacy") or 0) + computation.granted_units,
            )

    if computation.granted_units > 0:
        log_event(
            "Secretary", "Affinity",
            f"commander {commander_id}: ship {ship['ship_id']} (owned {ship['id']}) "
            f"+{computation.granted_units // INTIMACY_PER_AFFINITY_POINT} affinity "
            f"-> {new_intimacy // INTIMACY_PER_AFFINITY_POINT}",
            LOG_LEVEL_INFO,
        )
    return SecretaryAffinityGrant(
        owned_id=int(ship["id"]),
        ship_id=int(ship["ship_id"]),
        granted_units=computation.granted_units,
        intimacy=new_intimacy,
    )

async def secretary_affinity_loop(check_interval_seconds: int = 60) -> None:
    """Background ticker for ONLINE commanders (started from server entrypoint).

    Every ``check_interval_seconds`` it applies due secretary-affinity ticks to
    every connected commander and pushes ``SC_12019{intimacy}`` when a point
    was granted. Offline catch-up is handled at login (join_server).
    """
    from src.orm.active_commander import list_active_clients
    from src.protobuf import protobuf

    log_event("Secretary", "Affinity", "background tick loop started", LOG_LEVEL_INFO)
    while True:
        await asyncio.sleep(check_interval_seconds)
        try:
            clients = list_active_clients()
        except Exception as e:
            log_event("Secretary", "Affinity",
                      f"failed to snapshot active clients: {e}", LOG_LEVEL_ERROR)
            continue
        for commander_id, client in clients:
            try:
                grant = await tick_secretary_affinity(commander_id, client)
            except Exception as e:
                log_event("Secretary", "Affinity",
                          f"tick failed for commander {commander_id}: {e}", LOG_LEVEL_ERROR)
                continue
            if grant is None or grant.granted_units <= 0:
                continue
            try:
                await client.send_message(
                    12019, protobuf.SC_12019(intimacy=grant.intimacy)
                )
                log_event(
                    "Secretary", "Affinity",
                    f"pushed SC_12019 intimacy={grant.intimacy} "
                    f"to commander {commander_id}",
                    LOG_LEVEL_INFO,
                )
            except Exception as e:
                log_event("Secretary", "Affinity",
                          f"SC_12019 push failed for commander {commander_id}: {e}",
                          LOG_LEVEL_ERROR)



