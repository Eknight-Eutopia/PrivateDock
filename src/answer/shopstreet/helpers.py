import json
import random
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.db.store import get_default_store
from src.region.region import location as _region_location

DEFAULT_GOODS_COUNT = 10
DEFAULT_REFRESH_SECONDS = 24 * 60 * 60

# The goods table has PRIMARY KEY (commander_id, goods_id), so a list can only
# be corrupted by writes interleaving at statement level (delete + insert are
# separate autocommit statements). The lock serializes regeneration inside this
# process; _apply_goods_transactional wraps the write set in one DB transaction
# so even cross-process writers (e.g. the admin API on the same DB) replace the
# list atomically instead of merging two draws.
_REFRESH_LOCK = threading.Lock()

from src.config.game_variables import get_max_gear_skin_boxes, get_shopstreet_goods_count

# At most this many gear-skin-box offers (item type 11, e.g. the 7000-coin
# "Gear Skin Box (...)") may appear in one street list; the rest of the pool
# is normal offers, and without a cap roughly half of a 10-good draw is boxes.
# Configured in configurations/game_variables.json (max_gear_skin_boxes).
MAX_GEAR_SKIN_BOXES = get_max_gear_skin_boxes()
_LAST_LOADED_GEAR_SKIN_BOXES = MAX_GEAR_SKIN_BOXES


def _current_max_gear_skin_boxes() -> int:
    """Return the current gear skin boxes cap, syncing with config or module overrides."""
    cfg_cap = get_max_gear_skin_boxes()
    mod_cap = globals().get("MAX_GEAR_SKIN_BOXES")
    if mod_cap is not None and mod_cap != globals().get("_LAST_LOADED_GEAR_SKIN_BOXES", cfg_cap):
        return mod_cap
    globals()["_LAST_LOADED_GEAR_SKIN_BOXES"] = cfg_cap
    globals()["MAX_GEAR_SKIN_BOXES"] = cfg_cap
    return cfg_cap

_GEAR_SKIN_ITEM_IDS: Optional[set] = None


def _gear_skin_item_ids() -> set:
    """Item ids whose item config type == 11 (Gear/Equipment Skin Box)."""
    global _GEAR_SKIN_ITEM_IDS
    if _GEAR_SKIN_ITEM_IDS is None:
        from src.logger.logger import log_event, LOG_LEVEL_ERROR
        from src.orm.config_entry import list_config_entries_sync
        ids = set()
        try:
            entries = list_config_entries_sync(
                "sharecfgdata/item_data_statistics.json")
        except Exception as e:
            log_event("ShopStreet", "GearSkinBox",
                      f"failed to list item configs: {e}", LOG_LEVEL_ERROR)
            entries = []
        for entry in entries:
            data = getattr(entry, "data", None)
            if not isinstance(data, dict):
                try:
                    data = json.loads(data)
                except (ValueError, TypeError):
                    continue
            if not isinstance(data, dict):
                continue
            try:
                if int(data.get("type") or 0) == 11:
                    ids.add(str(data.get("id") or getattr(entry, "key", "")))
            except (TypeError, ValueError):
                continue
        _GEAR_SKIN_ITEM_IDS = ids
    return _GEAR_SKIN_ITEM_IDS


def _is_gear_skin_box_offer(offer: dict) -> bool:
    """True when the offer sells a gear-skin-box item (type 11)."""
    effects = offer.get("effects")
    if not effects:
        return False
    if isinstance(effects, str):
        try:
            effects = json.loads(effects)
        except (ValueError, TypeError):
            return False
    if not isinstance(effects, list):
        return False
    skin = _gear_skin_item_ids()
    return any(str(e) in skin for e in effects if isinstance(e, (int, str)))


_SHOP_STREET_REFRESH_HOURS = (0, 12, 18)


def _next_shop_street_refresh(now_unix: int) -> int:
    now = datetime.fromtimestamp(now_unix, tz=timezone.utc)
    local = now.astimezone(_region_location())
    base = local.replace(minute=0, second=0, microsecond=0)
    best = None
    for hour in _SHOP_STREET_REFRESH_HOURS:
        cand = base.replace(hour=hour)
        if cand <= local:
            cand = cand + timedelta(days=1)
        if best is None or cand < best:
            best = cand
    return int(best.timestamp())


def _is_local_midnight(ts_unix: int) -> bool:
    dt = datetime.fromtimestamp(ts_unix, tz=timezone.utc).astimezone(_region_location())
    return dt.hour == 0 and dt.minute == 0


def _should_reset_flash_count(next_flash_unix: int, now_unix: int) -> bool:
    """True if local midnight (00:00) has been reached or crossed since the last scheduled refresh."""
    if next_flash_unix <= 0 or now_unix < next_flash_unix:
        return False
    loc = _region_location()
    dt_flash = datetime.fromtimestamp(next_flash_unix, tz=timezone.utc).astimezone(loc)
    dt_now = datetime.fromtimestamp(now_unix, tz=timezone.utc).astimezone(loc)
    # 1. The scheduled refresh was 00:00 (midnight) and has arrived (now_unix >= next_flash_unix).
    # 2. Or the current date has advanced past the scheduled refresh date (offline across midnight).
    return (dt_flash.hour == 0 and dt_flash.minute == 0) or (dt_now.date() > dt_flash.date())


class RefreshOptions:
    def __init__(self, goods_count: Optional[int] = None,
                 next_flash_in_seconds: Optional[int] = None,
                 set_flash_count: Optional[int] = None,
                 seed: Optional[int] = None,
                 goods_ids: Optional[list[int]] = None,
                 discount_override: Optional[int] = None,
                 buy_count: Optional[int] = None):
        self.goods_count = goods_count
        self.next_flash_in_seconds = next_flash_in_seconds
        self.set_flash_count = set_flash_count
        self.seed = seed
        self.goods_ids = goods_ids or []
        self.discount_override = discount_override
        self.buy_count = buy_count


def refresh_if_needed(commander_id: int, now_unix: int):
    state, goods = ensure_state(commander_id, now_unix)
    target_count = get_shopstreet_goods_count()
    # Heal anything the schema alone cannot rule out: the PK forbids duplicate
    # goods ids, but a list longer than the draw size can only be corruption
    # (or an admin override), so regenerate it just like an empty one.
    if (now_unix >= state["next_flash_time"] or len(goods) == 0
            or len(goods) > target_count):
        reset_flash = _should_reset_flash_count(state["next_flash_time"], now_unix)
        options = RefreshOptions(
            goods_count=target_count,
            next_flash_in_seconds=DEFAULT_REFRESH_SECONDS,
            set_flash_count=0 if reset_flash else state.get("flash_count", 0),
            buy_count=1,
        )
        return refresh_goods_internal(commander_id, now_unix, options)
    return state, goods


def ensure_state(commander_id: int, now_unix: int):
    store = get_default_store()
    row = store.fetchrow(
        "SELECT commander_id, level, next_flash_time, level_up_time, flash_count FROM shopping_street_states WHERE commander_id = $1",
        commander_id
    )
    if row is None:
        next_flash = _next_shop_street_refresh(now_unix)
        store.execute(
            "INSERT INTO shopping_street_states (commander_id, level, next_flash_time, level_up_time, flash_count) "
            "VALUES ($1, 1, $2, 0, 0) ON CONFLICT (commander_id) DO NOTHING",
            commander_id, next_flash
        )
        state = {"commander_id": commander_id, "level": 1, "next_flash_time": next_flash, "level_up_time": 0, "flash_count": 0}
        options = RefreshOptions(
            goods_count=get_shopstreet_goods_count(),
            next_flash_in_seconds=DEFAULT_REFRESH_SECONDS,
            set_flash_count=0,
            buy_count=1,
        )
        goods = refresh_goods_internal(commander_id, now_unix, options)[1]
        return state, goods

    state = {"commander_id": row[0], "level": row[1], "next_flash_time": row[2], "level_up_time": row[3], "flash_count": row[4]}
    goods = load_goods(commander_id)
    return state, goods


def refresh_goods_internal(commander_id: int, now_unix: int, options: RefreshOptions):
    with _REFRESH_LOCK:
        state = load_or_create_state(commander_id, now_unix)
        goods = _refresh_goods(commander_id, now_unix, options)
        state = load_state(commander_id)
    return state, goods


def load_state(commander_id: int) -> dict:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT commander_id, level, next_flash_time, level_up_time, flash_count FROM shopping_street_states WHERE commander_id = $1",
        commander_id
    )
    if row is None:
        return {"commander_id": commander_id, "level": 1, "next_flash_time": 0, "level_up_time": 0, "flash_count": 0}
    return {"commander_id": row[0], "level": row[1], "next_flash_time": row[2], "level_up_time": row[3], "flash_count": row[4]}


def load_or_create_state(commander_id: int, now_unix: int) -> dict:
    state = load_state(commander_id)
    if state["next_flash_time"] == 0:
        next_flash = _next_shop_street_refresh(now_unix)
        store = get_default_store()
        store.execute(
            "INSERT INTO shopping_street_states (commander_id, level, next_flash_time, level_up_time, flash_count) "
            "VALUES ($1, 1, $2, 0, 0) ON CONFLICT (commander_id) DO NOTHING",
            commander_id, next_flash
        )
        state = {"commander_id": commander_id, "level": 1, "next_flash_time": next_flash, "level_up_time": 0, "flash_count": 0}
    return state


def load_goods(commander_id: int) -> list[dict]:
    store = get_default_store()
    rows = store.fetch(
        "SELECT commander_id, goods_id, discount, buy_count FROM shopping_street_goods WHERE commander_id = $1 ORDER BY goods_id ASC",
        commander_id
    )
    return [{"commander_id": r[0], "goods_id": r[1], "discount": r[2], "buy_count": r[3]} for r in rows]


def replace_goods(commander_id: int, goods: list[dict]):
    _apply_goods_transactional(commander_id, goods)


def resolve_offers(ids: list[int]) -> tuple[list[dict], list[int]]:
    if not ids:
        return [], []
    store = get_default_store()
    rows = store.fetch(
        "SELECT id, genre, discount FROM shop_offers WHERE id = ANY($1) AND genre = 'shopping_street'",
        ids
    )
    lookup = {}
    for r in rows:
        lookup[r[0]] = r
    ordered = []
    invalid = []
    for oid in ids:
        if oid in lookup:
            r = lookup[oid]
            ordered.append({"id": r[0], "genre": r[1], "discount": r[2]})
        else:
            invalid.append(oid)
    return ordered, invalid


def _apply_goods_transactional(commander_id: int, goods: list[dict],
                               flash_count: Optional[int] = None,
                               next_flash: Optional[int] = None):
    """Replace a commander's street goods in one transaction.

    The delete + inserts (+ optional state update) are committed atomically so
    a concurrent writer can never interleave between them and leave a merged
    list behind (``Store.sync_transaction`` pins one connection for the block).
    """
    store = get_default_store()
    with store.sync_transaction() as tx:
        tx.execute("DELETE FROM shopping_street_goods WHERE commander_id = $1",
                   commander_id)
        for g in goods:
            tx.execute(
                "INSERT INTO shopping_street_goods (commander_id, goods_id, discount, buy_count) "
                "VALUES ($1, $2, $3, $4)",
                commander_id, g["goods_id"], g["discount"], g["buy_count"]
            )
        if next_flash is not None:
            tx.execute(
                "UPDATE shopping_street_states SET flash_count = $1, next_flash_time = $2 "
                "WHERE commander_id = $3",
                flash_count, next_flash, commander_id
            )


def _refresh_goods(commander_id: int, now_unix: int, options: RefreshOptions) -> list[dict]:
    goods_count = options.goods_count if options.goods_count is not None else get_shopstreet_goods_count()
    flash_count = options.set_flash_count if options.set_flash_count is not None else 0
    buy_count = options.buy_count if options.buy_count is not None else 1

    if options.goods_ids:
        offers, _ = resolve_offers(options.goods_ids)
    else:
        offers = _get_shopping_street_offers()
        offers = _select_offers(offers, goods_count, options.seed)

    goods = _build_goods(commander_id, offers, buy_count, options.discount_override)
    _apply_goods_transactional(commander_id, goods, flash_count,
                               _next_shop_street_refresh(now_unix))
    return goods


def _get_shopping_street_offers() -> list[dict]:
    store = get_default_store()
    rows = store.fetch(
        "SELECT id, genre, discount, effects FROM shop_offers WHERE genre = 'shopping_street'"
    )
    return [{"id": r[0], "genre": r[1], "discount": r[2], "effects": r[3]} for r in rows]


def _select_offers(offers: list[dict], count: int, seed: Optional[int] = None) -> list[dict]:
    if len(offers) <= count:
        return offers
    shuffled = list(offers)
    rng = random.Random(seed)
    rng.shuffle(shuffled)

    # Walk the shuffled pool in order, but admit gear-skin boxes only while the
    # per-list budget lasts; once it is spent the remaining boxes are skipped
    # and the draw is topped up from later (normal) offers.
    selected = []
    box_budget = _current_max_gear_skin_boxes()
    for offer in shuffled:
        if len(selected) >= count:
            break
        if _is_gear_skin_box_offer(offer):
            if box_budget <= 0:
                continue
            box_budget -= 1
        selected.append(offer)

    # Safety: if the pool is box-heavy and normal offers ran out before the
    # draw was full, fill the remaining slots from the skipped boxes.
    if len(selected) < count:
        picked = set(id(o) for o in selected)
        for offer in shuffled:
            if len(selected) >= count:
                break
            if id(offer) in picked:
                continue
            selected.append(offer)
    return selected


def _build_goods(commander_id: int, offers: list[dict], buy_count: int, discount_override: Optional[int]) -> list[dict]:
    goods = []
    for offer in offers:
        discount = 100
        if discount_override is not None:
            discount = discount_override
        elif offer.get("discount", 0) > 0:
            discount = 100 - offer["discount"]
        goods.append({
            "commander_id": commander_id,
            "goods_id": offer["id"],
            "discount": discount,
            "buy_count": buy_count,
        })
    return goods
