import datetime
import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from src.protobuf import protobuf
from src.db.store import get_default_store
from src.orm.build import build_create


def build_time_for_ship(template_id: int) -> int:
    store = get_default_store()
    row = store.fetchrow("SELECT build_time FROM ships WHERE template_id = $1", template_id)
    return int(row["build_time"]) if row else 600


def make_build_info( pool_id: int, finishes_at: datetime.datetime,

                    now: datetime.datetime) -> "protobuf.BUILDINFO":
    secs = int((finishes_at - now).total_seconds())
    return protobuf.BUILDINFO(
        time=secs,
        finish_time=int(finishes_at.timestamp()),
        build_id=pool_id,
    )


def build_info_from_row(row: dict, now: Optional[datetime.datetime] = None) -> "protobuf.BUILDINFO":
    """BUILDINFO for one authoritative queue row.

    A started build carries its real remaining seconds; a queued (not-yet-
    started) build must carry its FULL build time, because the client uses the
    ``time`` field to start the countdown the moment a dock slot frees
    (``BuildShip.active()``: finishTime = serverTime + time).
    """
    from .helpers import BUILD_STATE_STARTED, remaining_seconds, _as_utc
    now = now or datetime.datetime.now(datetime.timezone.utc)
    finish = _as_utc(row.get("finishes_at"))
    if row.get("state", BUILD_STATE_STARTED) == BUILD_STATE_STARTED and finish is not None:
        secs = remaining_seconds(finish, now)
    else:
        secs = int(row.get("duration") or 0)
    return protobuf.BUILDINFO(
        time=secs,
        finish_time=int(finish.timestamp()) if finish else int(now.timestamp()),
        build_id=row.get("pool_id", 0),
    )


def create_build_record(client, commander_id: int, ship_id: int, pool_id: int,
                        finishes_at: datetime.datetime) -> Optional[dict]:
    """Insert a build row and append it to the live commander build list."""
    result = build_create(commander_id, ship_id, pool_id, finishes_at)
    if result is None:
        return None
    builds = getattr(client.commander, "builds", None)
    if builds is not None:
        builds.append(result)
    return result


def start_one_build(client, commander_id: int, ship_id: int, pool_id: int,
                    now: Optional[datetime.datetime] = None) -> Optional["protobuf.BUILDINFO"]:
    """Draw-resolved: build one timed construction for `ship_id` and return BUILDINFO."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    bt = build_time_for_ship(ship_id)
    finishes_at = now + datetime.timedelta(seconds=bt)
    created = create_build_record(client, commander_id, ship_id, pool_id, finishes_at)
    if created is None:
        return None
    return make_build_info(pool_id, finishes_at, now)


def pool_ships(pool_id: int) -> List[Tuple[int, int]]:
    """All (template_id, rarity_id) pairs belonging to a normal build pool.

    Membership is read from `build_pool_ships`, the (pool_id, template_id)
    join table the "Pools" importer fills from configurations/build_pools.json.
    A ship can be cross-listed in several pools (URs and older CAs/CLs appear
    in Heavy+Special or Light+Special), which the single ships.pool_id column
    (dropped in migration 0095) could not represent.
    """
    store = get_default_store()
    rows = store.fetch(
        "SELECT s.template_id, s.rarity_id FROM build_pool_ships b "
        "JOIN ships s ON s.template_id = b.template_id "
        "WHERE b.pool_id = $1 ORDER BY s.template_id",
        pool_id,
    )
    return [(r["template_id"], r["rarity_id"]) for r in rows]


# (gold, cube) cost per normal build pool id. Client pool ids: 1=Special, 2=Light,
# 3=Heavy. Event pools fall through to the Special cost.
def build_cost_normal(pool_id: int) -> Tuple[int, int]:
    if pool_id == 2:  # Light
        return 600, 1
    return 1500, 2  # Special / Heavy / Event


# (gold, cube) cost per Wishing Well create_id (ship_data_create_material[create_id]):
# gold = use_gold, cube = number_1 (item 20001).
CREATE_MATERIAL_COST = {6: (1500, 2), 7: (600, 1), 8: (1500, 2), 9: (600, 1)}


# Client parity: BuildShipCommand adds `count * material.exchange_count` to
# BuildShipProxy.regularExchangeCount (see buildshipcommand.lua). The server
# previously stored only the raw build count, so the client could show 400/400
# while the authoritative counter was still below the exchange threshold.
_EXCHANGE_POINT_FALLBACK = {
    1: 2,   # Special
    2: 1,   # Light
    3: 2,   # Heavy
    6: 2,   # Wishing Well - Special
    7: 1,   # Wishing Well - Light
    8: 2,   # Wishing Well - Heavy
    12: 2,
    13: 2,
}


@lru_cache(maxsize=8)
def _load_sharecfg(region: str, filename: str):
    from src.misc.update_data_helpers import DATA_DIR

    path = Path(DATA_DIR) / region / "ShareCfg" / filename
    with path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


@lru_cache(maxsize=8)
def _exchange_points_by_pool(region: str) -> dict[int, int]:
    try:
        data = _load_sharecfg(region, "ship_data_create_material.json")
        entries = data.values() if isinstance(data, dict) else data
        counts = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pool_id = int(entry.get("id") or 0)
            if pool_id:
                counts[pool_id] = max(0, int(entry.get("exchange_count") or 0))
        if counts:
            return counts
    except Exception:
        pass
    return dict(_EXCHANGE_POINT_FALLBACK)


def exchange_points_for_pool(pool_id: int) -> int:
    """Return the regular-exchange points granted by one build in a pool."""
    from src.region.region import current as current_region

    return _exchange_points_by_pool(current_region()).get(int(pool_id), 0)


@lru_cache(maxsize=8)
def _regular_exchange_request(region: str) -> int:
    try:
        data = _load_sharecfg(region, "ship_data_create_exchange.json")
        entries = data.values() if isinstance(data, dict) else data
        for entry in entries:
            if isinstance(entry, dict) and int(entry.get("id") or 0) == 1:
                return max(1, int(entry.get("exchange_request") or 400))
    except Exception:
        pass
    return 400


def regular_exchange_request() -> int:
    """Return the regular build-pool UR exchange threshold."""
    from src.region.region import current as current_region

    return _regular_exchange_request(current_region())


def build_cost_create_id(create_id: int) -> Tuple[int, int]:
    return CREATE_MATERIAL_COST.get(create_id, (1500, 2))
