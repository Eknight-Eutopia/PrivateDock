from __future__ import annotations
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.db.store import get_default_store
from src.orm.config_entry import fetch_config_entry_data, fetch_config_entries_data
from src.shopreset.framework import deterministic_seed
from src.shopreset.framework import guild_store_window as _guild_store_window
from src.rng.rng import LockedRand

GUILD_STORE_CONFIG_CATEGORY = "ShareCfg/guild_store.json"
GUILD_SET_CONFIG_CATEGORY = "ShareCfg/guildset.json"

# Regeneration is a delete + inserts + state update; the lock serializes it in
# this process and _save_goods runs it in one DB transaction so concurrent
# writers (other threads/processes) can never leave a merged goods list.
_REFRESH_LOCK = threading.Lock()


@dataclass
class StoreEntry:
    id: int = 0
    weight: int = 0
    goods_purchase_limit: int = 0
    ensure: int = 0
    order: int = 0


@dataclass
class SetEntry:
    key: str = ""
    key_value: int = 0
    key_args: list[int] = field(default_factory=list)


@dataclass
class Config:
    store_entries: list[StoreEntry] = field(default_factory=list)
    goods_count: int = 0
    refresh_limit: int = 0
    refresh_costs: list[int] = field(default_factory=list)

    def can_manual_refresh(self, current_count: int) -> bool:
        if self.refresh_limit == 0:
            return True
        return current_count < self.refresh_limit

    def refresh_cost(self, next_count: int) -> int:
        if next_count == 0 or not self.refresh_costs:
            return 0
        index = int(next_count - 1)
        if index >= len(self.refresh_costs):
            return self.refresh_costs[-1]
        return self.refresh_costs[index]


@dataclass
class RefreshOptions:
    refresh_count: int = 0
    next_refresh_time: int = 0


def load_config() -> Optional[Config]:
    store_rows = fetch_config_entries_data(GUILD_STORE_CONFIG_CATEGORY)
    entries = []
    for data in store_rows:
        if not isinstance(data, dict):
            continue
        entry = StoreEntry(
            id=data.get("id", 0),
            weight=data.get("weight", 0),
            goods_purchase_limit=data.get("goods_purchase_limit", 0),
            ensure=data.get("ensure", 0),
            order=data.get("order", 0),
        )
        if entry.id == 0:
            continue
        entries.append(entry)

    goods_count_entry = _get_guild_set_entry("store_goods_quantity")
    store_reset_time_entry = _get_guild_set_entry("store_reset_time")
    store_reset_cost_entry = _get_guild_set_entry("store_reset_cost")

    goods_count = goods_count_entry.key_value if goods_count_entry else 0
    refresh_limit = store_reset_time_entry.key_value if store_reset_time_entry and store_reset_time_entry.key_value > 0 else 1

    refresh_costs = list(store_reset_cost_entry.key_args) if store_reset_cost_entry else []
    if not refresh_costs:
        if store_reset_cost_entry and store_reset_cost_entry.key_value > 0:
            refresh_costs = [store_reset_cost_entry.key_value]
        else:
            refresh_costs = [0]

    if goods_count == 0:
        goods_count = 10

    return Config(
        store_entries=entries,
        goods_count=goods_count,
        refresh_limit=refresh_limit,
        refresh_costs=refresh_costs,
    )


def ensure_state(
    commander_id: int, now: datetime, config: Config
) -> tuple[dict, list[dict], Optional[Exception]]:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT commander_id, refresh_count, next_refresh_time FROM guild_shop_states WHERE commander_id = $1",
        commander_id,
    )
    if row is None:
        next_time = _next_guild_reset(now)
        store.execute(
            "INSERT INTO guild_shop_states (commander_id, refresh_count, next_refresh_time) VALUES ($1, $2, $3)",
            commander_id, 0, next_time,
        )
        goods = _refresh_goods_internal(
            commander_id, now, config,
            RefreshOptions(refresh_count=0, next_refresh_time=next_time),
        )[0]
        return {"commander_id": commander_id, "refresh_count": 0, "next_refresh_time": next_time}, goods, None

    state = {"commander_id": row[0], "refresh_count": row[1], "next_refresh_time": row[2]}
    goods = _load_goods_internal(commander_id)
    return state, goods, None


def refresh_if_needed(
    commander_id: int, now: datetime, config: Config
) -> tuple[dict, list[dict], Optional[Exception]]:
    state, goods, err = ensure_state(commander_id, now, config)
    if err:
        return None, None, err
    # The draw never exceeds config.goods_count slots; a different slot count
    # can only be corruption or outdated schema, so heal it on fetch.
    expected = config.goods_count if config else 0
    needs_refresh = (
        now.timestamp() >= state["next_refresh_time"]
        or len(goods) == 0
        or (expected > 0 and len(goods) != expected)
    )
    if not needs_refresh and config and config.store_entries:
        guaranteed_ids = {e.id for e in config.store_entries if e.ensure == 1}
        if guaranteed_ids:
            current_ids = {g["goods_id"] for g in goods}
            if not guaranteed_ids.issubset(current_ids):
                needs_refresh = True

    if needs_refresh:
        next_time = _next_guild_reset(now)
        goods = _refresh_goods_internal(
            commander_id, now, config,
            RefreshOptions(refresh_count=0, next_refresh_time=next_time),
        )[0]
        row = _get_state_row(commander_id)
        if row:
            state = {"commander_id": row[0], "refresh_count": row[1], "next_refresh_time": row[2]}
    return state, goods, None


def refresh_goods(
    commander_id: int, now: datetime, config: Config, options: RefreshOptions
) -> tuple[list[dict], Optional[Exception]]:
    with _REFRESH_LOCK:
        goods = _build_goods(commander_id, config, _refresh_seed(commander_id, now, options.refresh_count))
        _save_goods(commander_id, goods, options.refresh_count, options.next_refresh_time)
    return goods, None


def load_goods(commander_id: int) -> list[dict]:
    return _load_goods_internal(commander_id)


def _get_state_row(commander_id: int):
    store = get_default_store()
    return store.fetchrow(
        "SELECT commander_id, refresh_count, next_refresh_time FROM guild_shop_states WHERE commander_id = $1",
        commander_id,
    )


def _load_goods_internal(commander_id: int) -> list[dict]:
    store = get_default_store()
    rows = store.fetch(
        "SELECT commander_id, index, goods_id, count FROM guild_shop_goods WHERE commander_id = $1 ORDER BY index",
        commander_id,
    )
    return [
        {"commander_id": r[0], "index": r[1], "goods_id": r[2], "count": r[3]}
        for r in rows
    ]


def _save_goods(commander_id: int, goods: list[dict], refresh_count: int, next_refresh_time: int):
    store = get_default_store()
    with store.sync_transaction() as tx:
        tx.execute("DELETE FROM guild_shop_goods WHERE commander_id = $1", commander_id)
        for g in goods:
            tx.execute(
                "INSERT INTO guild_shop_goods (commander_id, index, goods_id, count) VALUES ($1, $2, $3, $4)",
                commander_id, g["index"], g["goods_id"], g["count"],
            )
        tx.execute(
            "UPDATE guild_shop_states SET refresh_count = $2, next_refresh_time = $3 WHERE commander_id = $1",
            commander_id, refresh_count, next_refresh_time,
        )


def _build_goods(commander_id: int, config: Config, seed: int) -> list[dict]:
    if config is None:
        return []
    entries = _select_goods(config.store_entries, int(config.goods_count), seed)
    return [
        {
            "commander_id": commander_id,
            "index": i + 1,
            "goods_id": e.id,
            "count": e.goods_purchase_limit if e.goods_purchase_limit > 0 else 1,
        }
        for i, e in enumerate(entries)
    ]


def _select_goods(entries: list[StoreEntry], count: int, seed: int) -> list[StoreEntry]:
    if count <= 0 or not entries:
        return []

    guaranteed = sorted([e for e in entries if e.ensure == 1], key=lambda e: e.id)
    if len(guaranteed) >= count:
        return guaranteed[:count]

    pool = [e for e in entries if e.ensure == 0]
    if not pool:
        pool = list(entries)

    remaining = count - len(guaranteed)
    rng = LockedRand(seed)
    total_weight = sum(e.weight if e.weight > 0 else 1 for e in pool)

    selected = list(guaranteed)
    for _ in range(remaining):
        roll = rng.uint32_n(total_weight)
        for e in pool:
            w = e.weight if e.weight > 0 else 1
            if roll < w:
                selected.append(e)
                break
            roll -= w

    return selected


def _get_guild_set_entry(key: str) -> Optional[SetEntry]:
    data = fetch_config_entry_data(GUILD_SET_CONFIG_CATEGORY, key)
    if not isinstance(data, dict):
        return None
    return SetEntry(
        key=data.get("key", ""),
        key_value=data.get("key_value", 0),
        key_args=data.get("key_args", []),
    )


def _next_guild_reset(now: datetime) -> int:
    try:
        w = _guild_store_window(now)
        return int(w.end.timestamp())
    except Exception:
        utc = now.astimezone(timezone.utc)
        return int((utc + timedelta(days=3)).timestamp())


def _refresh_seed(commander_id: int, now: datetime, refresh_count: int) -> int:
    try:
        w = _guild_store_window(now)
        return deterministic_seed(commander_id, w.key, refresh_count)
    except Exception:
        utc = now.astimezone(timezone.utc)
        return deterministic_seed(commander_id, int(utc.timestamp()), refresh_count)


_refresh_goods_internal = refresh_goods
