"""Helpers for the Military Exercise (PvP / Mock Battles) feature.

Implements persistent season state, attempt recovery, rival generation with
real battleable ship fleets, score/merit computation, and season pushes.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.logger.logger import log_event, LOG_LEVEL_ERROR
from src.protobuf import protobuf
from src.shopreset.framework import _current_region_location, daily_window, deterministic_seed
from src.answer.shipinfo.builder import build_ship_info
from src.orm.game_data import get_ship_template_config
from src.orm.exercise_state import ExerciseState, get_exercise_state_sync, upsert_exercise_state_sync


# --- Constants ---------------------------------------------------------------

EXERCISE_MAX_ATTEMPTS = 10
EXERCISE_RECOVER_AMOUNT = 5
EXERCISE_REFRESHES_PER_DAY = 5
EXERCISE_RIVAL_COUNT = 5
EXERCISE_SHIPS_PER_RIVAL = 6
EXERCISE_SEASON_DAYS = 14

# Rival fleet level. The Exercise battle is simulated entirely on the client;
# the server only supplies the rival SHIPINFO (the client computes the actual
# combat stats from template + level). 100 was unbeatable for a weak/early
# fleet, so keep rivals modest and beatable. Tune as desired.
EXERCISE_RIVAL_LEVEL = 30

# Merit (功勋) is resource id 3 in the game data ("exploit"; this is the
# resource_type of the Merit Shop goods in pg.shop_template, e.g. 43004
# "Exchange 10000 Merit for Universal Bulin MKII"). The client reads/spends
# Merit from this resource, so exercise rewards must grant it here.
EXERCISE_MERIT_RESOURCE_ID = 3

# Gems (the premium currency) are resource id 4 - same id used for chapter
# repair costs and mail-storeroom extension payments.
EXERCISE_GEM_RESOURCE_ID = 4

# Region-local recovery boundary hours (00:00, 12:00, 18:00).
RECOVERY_HOURS = (0, 12, 18)

# Ship types (pg.ship_data_template.type) grouped by team, transcribed
# from the client's ShipType.VanguardShipType / MainShipType / SubShipType
# (model/const/shiptype.lua). The client (model/vo/rival.lua) re-classifies
# every rival ship by getTeamType() into vanguardShips / mainShips and DROPS any
# ship that is neither (submarines 8/17/22 and special types 14/15/16). Exercise
# rivals must therefore be built from exactly 3 vanguard-type + 3 main-type
# ships, or the formation row renders empty ("only background").
VANGUARD_SHIP_TYPES = frozenset({1, 2, 3, 9, 11, 18, 19, 20, 23})
MAIN_SHIP_TYPES = frozenset({4, 5, 6, 7, 10, 12, 13, 21, 24})

EXERCISE_TIERS = [
    ("Private", 0, 50, 25, 25, 12),
    ("Petty Officer", 100, 60, 30, 22, 11),
    ("Ensign", 200, 70, 35, 20, 10),
    ("Lieutenant Junior Grade", 300, 70, 35, 17, 8),
    ("Lieutenant", 400, 70, 35, 15, 7),
    ("Lieutenant Commander", 550, 80, 40, 15, 7),
    ("Commander", 700, 80, 40, 15, 7),
    ("Captain", 850, 80, 40, 12, 6),
    ("Rear Admiral Lower Half", 1050, 90, 45, 10, 5),
    ("Rear Admiral", 1250, 90, 45, 10, 5),
    ("Vice Admiral", 1450, 90, 45, 10, 5),
    ("Admiral", 1650, 90, 45, 10, 5),
    ("Fleet Admiral", 1900, 90, 45, 10, 5),
    ("Admiral of the Navy", 2200, 100, 50, 10, 5),
]


# --- Time / season helpers --------------------------------------------------

def get_region_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(_current_region_location())


def region_day_key(now: Optional[datetime] = None) -> int:
    if now is None:
        now = get_region_now()
    return daily_window(now).key


def season_bounds(now: Optional[datetime] = None):
    """Return (season_id, season_start_ts, season_end_ts) for the 2-week block."""
    if now is None:
        now = get_region_now()
    loc = _current_region_location()
    local = now.astimezone(loc)
    monday = local - timedelta(days=local.weekday())
    monday_mid = datetime(monday.year, monday.month, monday.day, 0, 0, 0, 0, loc)
    epoch = datetime(2020, 1, 6, 0, 0, 0, 0, loc)  # a known Monday
    weeks = max(0, (monday_mid - epoch).days // 7)
    block = weeks // 2  # 2-week blocks
    season_start = epoch + timedelta(weeks=block * 2)
    season_end = season_start + timedelta(days=EXERCISE_SEASON_DAYS)
    season_id = block + 1
    return (
        season_id,
        int(season_start.astimezone(timezone.utc).timestamp()),
        int(season_end.astimezone(timezone.utc).timestamp()),
    )


def next_recover_boundary(now: Optional[datetime] = None) -> int:
    """Next region-local recovery time (00:00 / 12:00 / 18:00) >= now."""
    if now is None:
        now = get_region_now()
    loc = _current_region_location()
    local = now.astimezone(loc)
    for hour in RECOVERY_HOURS:
        candidate = local.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate < local:
            continue
        return int(candidate.astimezone(timezone.utc).timestamp())
    nxt = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(nxt.astimezone(timezone.utc).timestamp())


def tier_index_for_score(score: int) -> int:
    """1-based tier index for a seasonal score (1 = lowest)."""
    idx = 1
    for i, tier in enumerate(EXERCISE_TIERS):
        if score >= tier[1]:
            idx = i + 1
    return idx


# --- State recompute --------------------------------------------------------

def recompute_state(state: ExerciseState, now: Optional[datetime] = None) -> ExerciseState:
    """Apply season reset, attempt recovery and daily refresh reset in place."""
    if now is None:
        now = get_region_now()
    now_ts = int(now.astimezone(timezone.utc).timestamp())

    # Season reset (by time).
    sid, s_start, s_end = season_bounds(now)
    if state.season_end == 0 or now_ts >= state.season_end:
        state.season_id = sid
        state.season_end = s_end
        state.score = 0
        state.fight_count = EXERCISE_MAX_ATTEMPTS
        state.rewarded_rank = 0

    # Attempt recovery at 00:00 / 12:00 / 18:00.
    # The boundary timer must ALWAYS advance past now, even while at max count.
    # Guarding the loop with fight_count < MAX left next_recover_time stale in
    # the past when a boundary passed at 10/10, so every later battle was
    # immediately refunded (10 -> 9 -> +5 -> 10) and the count never dropped.
    if state.next_recover_time == 0:
        state.next_recover_time = next_recover_boundary(now)
    while now_ts >= state.next_recover_time:
        if state.fight_count < EXERCISE_MAX_ATTEMPTS:
            from src.config.game_variables import get_exercise_recover_amount
            state.fight_count = min(EXERCISE_MAX_ATTEMPTS, state.fight_count + get_exercise_recover_amount())
        state.next_recover_time = _advance_recover_boundary(state.next_recover_time)

    # Daily "New Opponents" refresh count reset.
    key = region_day_key(now)
    if state.last_refresh_day != key:
        from src.config.game_variables import get_exercise_refreshes_per_day
        state.refreshes_today = get_exercise_refreshes_per_day()
        state.last_refresh_day = key

    return state


def _advance_recover_boundary(ts: int) -> int:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(_current_region_location())
    for hour in RECOVERY_HOURS:
        cand = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
        if cand > dt:
            return int(cand.astimezone(timezone.utc).timestamp())
    nxt = (dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(nxt.astimezone(timezone.utc).timestamp())


def ensure_exercise_state(commander_id: int, now: Optional[datetime] = None) -> ExerciseState:
    state = get_exercise_state_sync(commander_id)
    if state is None:
        from src.config.game_variables import get_exercise_refreshes_per_day
        state = ExerciseState(
            commander_id=commander_id,
            season_id=1,
            season_end=0,
            score=0,
            merit=0,
            fight_count=EXERCISE_MAX_ATTEMPTS,
            next_recover_time=0,
            refreshes_today=get_exercise_refreshes_per_day(),
            last_refresh_day=0,
            rewarded_rank=0,
        )
    recompute_state(state, now)
    upsert_exercise_state_sync(state)
    return state


# --- NPC rival generation ---------------------------------------------------

# Cached (vanguard_ids, main_ids) ship-template pools, lazily loaded from the
# DB. Exercises need a fixed 3 vanguard + 3 main composition per rival, so we
# pre-partition the available ships by team type once.
#
# template_id >= 900000 ships are shadow/enemy-only copies ("Denver", "Tartu",
# the "Hero" placeholder, per-stage enemy reskins) used as enemies in levels;
# a player can never own them, so they are excluded from NPC rival fleets.
@dataclass(frozen=True)
class NpcShipGroup:
    group_id: int               # template_id // 10
    english_name: str
    templates: tuple[int, ...]  # sorted tuple of template_ids

    def __ge__(self, other: int) -> bool:
        return any(t >= other for t in self.templates)

    def __lt__(self, other: int) -> bool:
        return all(t < other for t in self.templates)


STAGE_MIN_LEVEL = {
    1: 1,
    2: 10,
    3: 30,
    4: 70,
}


def _best_ship_template_id(templates: tuple[int, ...] | list[int], level: int) -> int:
    """Pick the highest-star ship template id available for the given level.

    Stage requirements based on the last digit of template_id:
      Stage 1 (*..): any level (level >= 1)
      Stage 2 (**..): level >= 10
      Stage 3 (***..): level >= 30
      Stage 4 (****..): level >= 70
    """
    valid = [tid for tid in templates if STAGE_MIN_LEVEL.get(tid % 10, 1) <= level]
    if valid:
        return max(valid, key=lambda tid: tid % 10)
    return min(templates, key=lambda tid: tid % 10)


_NPC_SHIP_POOLS: Optional[tuple[list[NpcShipGroup], list[NpcShipGroup]]] = None


def _npc_ship_pools() -> tuple[list[NpcShipGroup], list[NpcShipGroup]]:
    global _NPC_SHIP_POOLS
    if _NPC_SHIP_POOLS is not None:
        return _NPC_SHIP_POOLS
    from src.db.store import Store
    store = Store()
    allowed = ",".join(str(t) for t in (VANGUARD_SHIP_TYPES | MAIN_SHIP_TYPES))
    rows = store.fetch(
        "SELECT s.template_id, s.type, s.english_name "
        "FROM ships s "
        "WHERE s.type IN (%s) AND s.template_id < 900000 "
        "ORDER BY s.template_id" % allowed
    )
    groups: dict[int, dict] = {}
    for r in rows:
        tid, stype, ename = int(r[0]), int(r[1]), str(r[2] or "")
        gid = tid // 10
        if gid not in groups:
            groups[gid] = {
                "group_id": gid,
                "english_name": ename,
                "stype": stype,
                "templates": [],
            }
        groups[gid]["templates"].append(tid)

    vanguard: list[NpcShipGroup] = []
    main: list[NpcShipGroup] = []
    for g in groups.values():
        item = NpcShipGroup(
            group_id=g["group_id"],
            english_name=g["english_name"],
            templates=tuple(sorted(g["templates"])),
        )
        if g["stype"] in VANGUARD_SHIP_TYPES:
            vanguard.append(item)
        elif g["stype"] in MAIN_SHIP_TYPES:
            main.append(item)

    _NPC_SHIP_POOLS = (vanguard, main)
    return _NPC_SHIP_POOLS


def _sample_team(
    rng: random.Random,
    pool: list[NpcShipGroup],
    n: int,
    used_groups: set[int],
    used_names: set[str],
    base_level: float,
) -> list[tuple[int, int]]:
    """Pick n distinct (template_id, ship_level) pairs from a team pool.

    Ensures no collisions with already used ship groups (template_id // 10)
    or english_names across the entire rival fleet.
    Each ship's level is determined by _npc_ship_level(rng, base_level),
    and the ship's template is selected as the maximum available star stage
    for that level. Groups with no valid stage for the generated level
    (e.g. standalone retrofit stages requiring level 70+) are skipped.
    """
    selected: list[tuple[int, int]] = []
    if not pool:
        return selected

    candidates = rng.sample(pool, len(pool))
    for group in candidates:
        if group.group_id in used_groups:
            continue
        if group.english_name and group.english_name in used_names:
            continue
        lvl = _npc_ship_level(rng, base_level)
        valid = [tid for tid in group.templates if STAGE_MIN_LEVEL.get(tid % 10, 1) <= lvl]
        if not valid:
            continue
        sid = max(valid, key=lambda tid: tid % 10)
        selected.append((sid, lvl))
        used_groups.add(group.group_id)
        if group.english_name:
            used_names.add(group.english_name)
        if len(selected) == n:
            break

    # Fallback if pool had fewer non-colliding options than n
    if len(selected) < n:
        for group in candidates:
            if group.group_id not in used_groups:
                lvl = _npc_ship_level(rng, base_level)
                sid = _best_ship_template_id(group.templates, lvl)
                selected.append((sid, lvl))
                used_groups.add(group.group_id)
                if len(selected) == n:
                    break
    while len(selected) < n:
        group = rng.choice(pool)
        lvl = _npc_ship_level(rng, base_level)
        sid = _best_ship_template_id(group.templates, lvl)
        selected.append((sid, lvl))

    return selected


def _player_top6_avg_level(commander_id: int) -> float:
    """Average level of the player's 6 highest-level owned ships.

    Used as the base for NPC rival ship levels (avg +/- 10%). Falls back to
    EXERCISE_RIVAL_LEVEL when the player owns no ships yet.
    """
    from src.db.store import Store
    store = Store()
    rows = store.fetch(
        "SELECT level FROM owned_ships WHERE owner_id = %d "
        "AND deleted_at IS NULL ORDER BY level DESC LIMIT 6" % int(commander_id)
    )
    levels = [int(r[0]) for r in rows] if rows else []
    if not levels:
        from src.config.game_variables import get_exercise_rival_fallback_level
        return float(get_exercise_rival_fallback_level())
    return sum(levels) / len(levels)


def _npc_ship_level(rng: random.Random, base: float) -> int:
    """NPC ship level = player top-6 average scaled by configured min/max range."""
    from src.config.game_variables import get_exercise_bot_level_range

    low, high = get_exercise_bot_level_range()
    return max(1, int(round(base * rng.uniform(low, high))))


@dataclass(frozen=True)
class BaseEquipmentChain:
    base_id: int
    type: int
    ship_type_forbidden: frozenset[int]
    equip_limit: int
    chain: tuple[int, ...]


_EQUIPMENT_CHAINS: Optional[list[BaseEquipmentChain]] = None


def _equipment_chains() -> list[BaseEquipmentChain]:
    global _EQUIPMENT_CHAINS
    if _EQUIPMENT_CHAINS is not None:
        return _EQUIPMENT_CHAINS
    from src.db.store import Store
    store = Store()
    rows = store.fetch(
        "SELECT id, base, type, level, ship_type_forbidden, equip_limit "
        "FROM equipments ORDER BY level, id"
    )
    bases: dict[int, dict] = {}
    mods: dict[int, list[tuple[int, int]]] = {}
    for r in rows:
        eid = int(r[0])
        base = int(r[1]) if r[1] is not None else None
        etype = int(r[2] or 0)
        level = int(r[3] or 0)
        forbidden_raw = r[4]
        limit = int(r[5] or 0)
        if base is None:
            forbidden = set()
            if forbidden_raw:
                try:
                    val = json.loads(forbidden_raw) if isinstance(forbidden_raw, str) else forbidden_raw
                    if isinstance(val, (list, tuple)):
                        forbidden = {int(x) for x in val}
                except Exception:
                    pass
            bases[eid] = {
                "base_id": eid,
                "type": etype,
                "ship_type_forbidden": frozenset(forbidden),
                "equip_limit": limit,
                "chain": [eid],
            }
        else:
            mods.setdefault(base, []).append((level, eid))

    for base_id, mod_list in mods.items():
        if base_id in bases:
            mod_list.sort(key=lambda x: (x[0], x[1]))
            bases[base_id]["chain"].extend([m[1] for m in mod_list])

    _EQUIPMENT_CHAINS = [
        BaseEquipmentChain(
            base_id=b["base_id"],
            type=b["type"],
            ship_type_forbidden=b["ship_type_forbidden"],
            equip_limit=b["equip_limit"],
            chain=tuple(b["chain"]),
        )
        for b in bases.values()
    ]
    return _EQUIPMENT_CHAINS


def _scale_equipment(chain: tuple[int, ...] | list[int], level: int) -> int:
    """Scale equipment from base (chain[0]) to max modification (chain[-1]) based on ship level (1-125).

    Example for chain [500..513] (len 14):
      level 1 -> 500 (base)
      level 100 -> 510 (+10 modification)
      level 125 -> 513 (max modification)
    """
    if not chain:
        return 0
    if len(chain) == 1 or level <= 1:
        return chain[0]
    ratio = max(0.0, min(1.0, level / 125.0))
    idx = int(round(ratio * (len(chain) - 1)))
    idx = max(0, min(idx, len(chain) - 1))
    return chain[idx]


def _generate_npc_ship_equip_overrides(
    template_id: int,
    level: int,
    rng: Optional[random.Random] = None,
) -> dict[int, tuple[int, int]]:
    """Select suitable equipment for each ship slot and scale it according to ship level.

    Slot matching rules:
      1. Equipment type must be in the slot's allowed types (cfg[f"equip_{pos}"]).
      2. Ship type must not be in the equipment's ship_type_forbidden.
      3. Base equipment is not duplicated across slots, and equip_limit is respected.
      4. Equipment is scaled along its modification chain based on ship level.
    """
    cfg = get_ship_template_config(template_id)
    if not cfg:
        return {pos: (0, 0) for pos in range(1, 6)}

    ship_type = int(cfg.get("type", 0) or 0)
    all_chains = _equipment_chains()

    used_bases: set[int] = set()
    used_limits: set[int] = set()
    equip_overrides: dict[int, tuple[int, int]] = {}

    for pos in range(1, 6):
        allowed = cfg.get(f"equip_{pos}")
        if not allowed or not isinstance(allowed, (list, tuple)):
            equip_overrides[pos] = (0, 0)
            continue
        allowed_set = set(allowed)

        # Candidates matching slot types, not forbidden for ship type, not already used
        candidates = [
            b for b in all_chains
            if b.type in allowed_set
            and ship_type not in b.ship_type_forbidden
            and b.base_id not in used_bases
            and (b.equip_limit == 0 or b.equip_limit not in used_limits)
        ]

        # Fallback if all distinct bases were used (e.g. repeated auxiliary slots)
        if not candidates:
            candidates = [
                b for b in all_chains
                if b.type in allowed_set
                and ship_type not in b.ship_type_forbidden
            ]

        if candidates:
            chosen = rng.choice(candidates) if rng is not None else candidates[0]
            used_bases.add(chosen.base_id)
            if chosen.equip_limit > 0:
                used_limits.add(chosen.equip_limit)
            equip_id = _scale_equipment(chosen.chain, level)
            equip_overrides[pos] = (equip_id, 0)
        else:
            equip_overrides[pos] = (0, 0)

    return equip_overrides


def build_npc_shipinfo(
    template_id: int, level: int = 125, rng: Optional[random.Random] = None
) -> protobuf.SHIPINFO:
    cfg = get_ship_template_config(template_id)
    max_level = (cfg or {}).get("max_level") or (cfg or {}).get("level") or 125
    # Keep NPC ship levels valid: never above the ship's natural max level.
    level = max(1, min(int(level), max_level))
    row = (
        template_id,   # id
        template_id,   # template_id
        level,         # level
        0,             # exp
        100,           # energy
        0,             # intimacy
        0,             # skin_id
        max_level,     # max_level
        0,             # is_locked
        0,             # propose
        0,             # common_flag
        0,             # activity_npc
        0,             # create_time (required field; NPC ships have no real timestamp)
        "",            # name
        None,          # change_name_timestamp
        1,             # state
        0, 0, 0, 0,    # state_info 1-4
        0,             # proficiency
    )
    equip_overrides = _generate_npc_ship_equip_overrides(template_id, level, rng)
    # SHIPINFO building lives in ONE place (src/answer/shipinfo/builder.py);
    # NPC rival ships differ only in their synthetic default equip slots
    # (passed via equip_overrides, since NPC ships have no DB equipment).
    return build_ship_info(row, equip_overrides=equip_overrides)


def empty_display() -> "protobuf.DISPLAYINFO":
    """Build a well-formed DISPLAYINFO.

    The generated descriptor marks every DISPLAYINFO field as a proto2
    REQUIRED message field, so an empty ``DISPLAYINFO()`` is invalid and
    cannot be serialized.  The client ignores this field, so we populate the
    required fields with zeros to keep the message well-formed on both the
    server (Python serializer) and client (pbc) sides.
    """
    disp = protobuf.DISPLAYINFO()
    disp.icon = 0
    disp.skin = 0
    disp.icon_frame = 0
    disp.chat_frame = 0
    disp.icon_theme = 0
    disp.marry_flag = 0
    disp.transform_flag = 0
    return disp


def build_exercise_rival_target_list(
    commander_id: int, state: ExerciseState, now: Optional[datetime] = None, refresh_count: int = 0
) -> list:
    if now is None:
        now = get_region_now()
    day_key = region_day_key(now)
    # Include state.score in the seed so the rival fleets are tied to the
    # player's seasonal score. A duel always changes the score (win or loss),
    # so after every Exercise battle the rivals regenerate into a fresh set --
    # the defeated opponent (and the others) no longer show the same fleets.
    # Manual "New Opponents" (refresh_count) still independently re-rolls them.
    rng = random.Random(deterministic_seed(commander_id, day_key, refresh_count, state.score))
    vanguard_pool, main_pool = _npc_ship_pools()
    # Fallback if the ship pools are unavailable (e.g. config not loaded).
    if not vanguard_pool or not main_pool:
        fallback_v = [
            NpcShipGroup(group_id=10117, english_name="USS Brooklyn", templates=(101171,)),
            NpcShipGroup(group_id=10206, english_name="USS Atlanta", templates=(102061,)),
            NpcShipGroup(group_id=10306, english_name="USS Portland", templates=(103061,)),
        ]
        fallback_m = [
            NpcShipGroup(group_id=10401, english_name="USS Nevada", templates=(104011,)),
            NpcShipGroup(group_id=10501, english_name="USS Pennsylvania", templates=(105011,)),
            NpcShipGroup(group_id=10601, english_name="USS Long Island", templates=(106011,)),
        ]
        vanguard_pool = list(fallback_v)
        main_pool = list(fallback_m)
    rank = tier_index_for_score(state.score)
    # NPC ship level base: average level of the player's 6 highest-level ships,
    # each rival ship then gets base +/- 10% (see _npc_ship_level).
    base_level = _player_top6_avg_level(commander_id)
    targets = []
    for i in range(EXERCISE_RIVAL_COUNT):
        rival_id = 90000000 + i + refresh_count * 1000
        t = protobuf.TARGETINFO()
        t.id = rival_id
        t.level = 100
        t.name = ""
        t.score = state.score
        t.rank = rank
        # Exactly 3 vanguard-type + 3 main-type ships, placed in fixed
        # formation slots (vanguard[0..2] -> front row, main[0..2] -> back row).
        # Avoid duplicate ships across the whole rival fleet (vanguard + main)
        # by checking both group_id (template_id // 10) and english_name.
        used_groups: set[int] = set()
        used_names: set[str] = set()
        vanguard = _sample_team(rng, vanguard_pool, 3, used_groups, used_names, base_level)
        main = _sample_team(rng, main_pool, 3, used_groups, used_names, base_level)
        for sid, lvl in vanguard:
            t.vanguard_ship_list.append(build_npc_shipinfo(sid, lvl, rng=rng))
        for sid, lvl in main:
            t.main_ship_list.append(build_npc_shipinfo(sid, lvl, rng=rng))
        t.display.CopyFrom(empty_display())
        # The client (PlayerAttire.Flush) derives the rival portrait from
        # TARGETINFO.icon, which the EN TARGETINFO proto does NOT carry, so it
        # falls back to display.icon. Without a valid ship template id here the
        # MilitaryExerciseScene updateRival -> updateDrop(DROP_TYPE_SHIP, id=nil)
        # crashes ("attempt to index a nil value" in Drop:InitConfig). Use the
        # first main-fleet ship as the portrait icon.
        icon_ship = (
            t.main_ship_list[0].template_id
            if t.main_ship_list
            else (t.vanguard_ship_list[0].template_id if t.vanguard_ship_list else 0)
        )
        t.display.icon = int(icon_ship or 0)
        targets.append(t)
    return targets


# --- Season push ------------------------------------------------------------

def build_exercise_season_push_update(
    commander_id: int, state: Optional[ExerciseState] = None, now: Optional[datetime] = None,
    refresh_count: int = 0,
) -> protobuf.SC_18005:
    if state is None:
        state = ensure_exercise_state(commander_id, now)
    if now is None:
        now = get_region_now()
    response = protobuf.SC_18005()
    response.score = state.score
    response.rank = tier_index_for_score(state.score)
    targets = build_exercise_rival_target_list(commander_id, state, now, refresh_count)
    response.target_list.extend(targets)
    return response


def current_exercise_season_score_and_rank(commander_id: int):
    state = ensure_exercise_state(commander_id)
    return state.score, tier_index_for_score(state.score)


# --- Battle result ----------------------------------------------------------

def _rank_reward_merit(tier_index: int) -> int:
    """Merit granted for reaching a NEW highest rank tier (once per season).

    Amounts are the original 'Merit (Promotion)' column of the Military
    Exercise table, kept in configurations/exercise_rank_rewards.json."""
    import json
    import os

    cur = os.path.dirname(os.path.abspath(__file__))
    data = None
    for _ in range(6):
        cand = os.path.join(cur, "configurations", "exercise_rank_rewards.json")
        if os.path.exists(cand):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    if not isinstance(data, dict):
        return 0
    tiers = data.get("tiers") or {}
    return int(tiers.get(str(tier_index)) or 0)


def _rank_reward_resource_id() -> int:
    """Currency resource for the promotion reward mail (default: Merit = 3)."""
    import json
    import os

    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        cand = os.path.join(cur, "configurations", "exercise_rank_rewards.json")
        if os.path.exists(cand):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    return int((json.load(f) or {}).get("currency_resource_id") or EXERCISE_MERIT_RESOURCE_ID)
            except Exception:
                break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return EXERCISE_MERIT_RESOURCE_ID


def _send_rank_reward_mail(commander_id: int, tier_index: int, merit: int) -> Optional[int]:
    """Deliver the promotion reward via in-game mail (mails + mail_attachments).
    Attachment type 1 = resource; the currency comes from the config
    (original table: Merit)."""
    try:
        from src.orm.mail import create_mail_sync, create_mail_attachment_sync
        tier_name = EXERCISE_TIERS[tier_index - 1][0] if 1 <= tier_index <= len(EXERCISE_TIERS) else "?"
        mail_id = create_mail_sync(
            commander_id,
            title="Exercise Promotion Reward",
            body=(
                f"Congratulations, Commander!\nYou have been promoted to "
                f"{tier_name} in this season's Military Exercise.\n"
                "Please collect your attached Merit reward."
            ),
            custom_sender="",
        )
        if mail_id:
            create_mail_attachment_sync(
                mail_id,
                att_type=1,
                item_id=_rank_reward_resource_id(),
                quantity=merit,
            )
        return mail_id
    except Exception:
        return None


def apply_exercise_result(
    commander_id: int, won: bool, now: Optional[datetime] = None
) -> dict:
    """Apply a duel result: update score, merit and attempt count.

    Reaching a NEW highest rank tier for the current season mails out a gem
    reward once (tracked via exercise_states.rewarded_rank).

    Returns a dict with the computed deltas and the new state snapshot.
    """
    state = ensure_exercise_state(commander_id, now)
    if now is None:
        now = get_region_now()
    old_rank = tier_index_for_score(state.score)
    rewarded_rank = getattr(state, "rewarded_rank", 0) or 0
    tier = EXERCISE_TIERS[old_rank - 1]
    score_win, score_lose = tier[4], tier[5]
    merit_win, merit_lose = tier[2], tier[3]

    score_gain = score_win if won else score_lose
    merit_gain = merit_win if won else merit_lose

    state.score = max(0, state.score + score_gain)
    state.merit = state.merit + merit_gain
    state.fight_count = max(0, state.fight_count - 1)
    recompute_state(state, now)

    new_rank = tier_index_for_score(state.score)
    rank_reward_mailed = None
    try:
        if new_rank > max(rewarded_rank, old_rank):
            reward = _rank_reward_merit(new_rank)
            if reward > 0:
                if _send_rank_reward_mail(commander_id, new_rank, reward):
                    rank_reward_mailed = {"rank": new_rank, "merit": reward}
            # Mark as rewarded even when the tier grants 0, so each tier's
            # mail fires exactly once per season. The reward-mail step must
            # NEVER abort the score/merit persistence below (a failure here
            # used to freeze the player's score at the tier boundary).
            state.rewarded_rank = new_rank
    except Exception as e:
        log_event("Exercise", "RankRewardError",
                  f"rank-up reward failed for cmd {commander_id} rank {new_rank}: {e}",
                  LOG_LEVEL_ERROR)
    upsert_exercise_state_sync(state)

    # The client reads the player's Merit balance from resource id 3
    # ("exploit" in the game data; resource_type of the Merit Shop goods in
    # pg.shop_template). SC_18005 (score/rank/target_list) carries NO merit
    # field and SeasonInfo has none either, so the only way the client can
    # display / spend Merit is as a resource. Grant it here.
    try:
        from src.orm.resource import add_resource
        add_resource(commander_id, EXERCISE_MERIT_RESOURCE_ID, merit_gain)
    except Exception:
        pass

    return {
        "won": won,
        "score_gain": score_gain,
        "merit_gain": merit_gain,
        "score": state.score,
        "merit": state.merit,
        "rank": new_rank,
        "fight_count": state.fight_count,
        "reset_time": state.next_recover_time,
        "rank_reward_mailed": rank_reward_mailed,
    }


# --- Defense fleet / ownership (ported from previous helpers) ----------------

def load_exercise_fleet_ids(commander_id: int):
    from src.orm.exercise_fleet import get_exercise_fleet_sync
    vanguard, main = get_exercise_fleet_sync(commander_id)
    if vanguard is None:
        return [], []
    return vanguard, main


def owns_all_ships(commander_id: int, ship_ids) -> bool:
    from src.orm.owned_ship import list_ships_by_ids
    all_ids = [s for s in ship_ids if s]
    if not all_ids:
        return True
    rows = list_ships_by_ids(commander_id, all_ids)
    owned = {int(r[0]) for r in rows}
    return all(sid in owned for sid in all_ids)
