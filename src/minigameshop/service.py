from __future__ import annotations
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.db.store import get_default_store
from src.orm.config_entry import fetch_config_entries_data
from src.orm.mini_game_shop import (
    create_mini_game_shop_state,
    get_mini_game_shop_good_count,
    get_mini_game_shop_state,
    increment_mini_game_shop_good_buy_count,
    list_mini_game_shop_goods,
    refresh_mini_game_shop_goods,
)
from src.consts.drop_types import (
    DROP_TYPE_RESOURCE,
    DROP_TYPE_ITEM,
    DROP_TYPE_SHIP,
    DROP_TYPE_SKIN,
)

GAME_ROOM_SHOP_CATEGORY = "ShareCfg/gameroom_shop_template.json"
MINI_GAME_SHOP_TICKET_RESOURCE_ID = 12

# Regeneration is a delete + inserts + state update; the lock serializes it in
# this process and _save_goods runs it in one DB transaction so concurrent
# writers (other threads/processes) can never leave a merged goods list.
_REFRESH_LOCK = threading.Lock()


class MiniGameShopError(Exception):
    pass


class InvalidPurchasePayload(MiniGameShopError):
    pass


class InsufficientTickets(MiniGameShopError):
    pass


class SoldOut(MiniGameShopError):
    pass


class UnsupportedReward(MiniGameShopError):
    pass


@dataclass
class shopEntry:
    id: int = 0
    goods_purchase_limit: int = 0
    goods: list[int] = field(default_factory=list)
    drop_type: int = 0
    price: int = 0
    num: int = 0
    time: list = field(default_factory=list)
    order: int = 0


@dataclass
class PurchaseSelection:
    id: int = 0
    num: int = 0


@dataclass
class PurchaseDrop:
    type: int = 0
    id: int = 0
    number: int = 0


@dataclass
class Config:
    goods: list[shopEntry] = field(default_factory=list)


@dataclass
class RefreshOptions:
    next_refresh_time: int = 0


def load_config(now: datetime) -> Optional[Config]:
    rows = fetch_config_entries_data(GAME_ROOM_SHOP_CATEGORY)
    goods = []
    for data in rows:
        if not isinstance(data, dict):
            continue
        entry = shopEntry(
            id=data.get("id", 0),
            goods_purchase_limit=data.get("goods_purchase_limit", 0),
            goods=data.get("goods", []),
            drop_type=data.get("drop_type", 0),
            price=data.get("price", 0),
            num=data.get("num", 0),
            time=data.get("time", []),
            order=data.get("order", 0),
        )
        if entry.id == 0:
            continue
        if not _is_within_time(now, entry.time):
            continue
        goods.append(entry)
    goods.sort(key=lambda g: (g.order, g.id))
    return Config(goods=goods)


def ensure_state(
    commander_id: int, now: datetime, config: Config
) -> tuple[dict, list[dict], Optional[Exception]]:
    state = get_mini_game_shop_state(commander_id)
    if state is None:
        next_time = _next_daily_reset(now)
        create_mini_game_shop_state(commander_id, next_time)
        goods = _refresh_goods_internal(
            commander_id, config, RefreshOptions(next_refresh_time=next_time),
        )[0]
        return {"commander_id": commander_id, "next_refresh_time": next_time}, goods, None

    goods = _load_goods_internal(commander_id)
    return state, goods, None


def refresh_if_needed(
    commander_id: int, now: datetime, config: Config
) -> tuple[dict, list[dict], Optional[Exception]]:
    state, goods, err = ensure_state(commander_id, now, config)
    if err:
        return None, None, err
    # The refresh always writes exactly the config's goods; a longer list can
    # only be corruption (or a merged interleaved write), so heal it on fetch.
    expected = len(config.goods) if config else 0
    if (now.timestamp() >= state["next_refresh_time"] or len(goods) == 0
            or (expected > 0 and len(goods) > expected)):
        goods = _refresh_goods_internal(
            commander_id, config, RefreshOptions(next_refresh_time=_next_daily_reset(now)),
        )[0]
        refreshed = get_mini_game_shop_state(commander_id)
        if refreshed:
            state = refreshed
    return state, goods, None


def refresh_goods(
    commander_id: int, config: Config, options: RefreshOptions
) -> tuple[list[dict], Optional[Exception]]:
    with _REFRESH_LOCK:
        goods = _build_goods(commander_id, config)
        _save_goods(commander_id, goods, options.next_refresh_time)
    return goods, None


def force_refresh(
    commander_id: int, now: datetime, config: Config
) -> tuple[dict, list[dict], Optional[Exception]]:
    _, _, err = ensure_state(commander_id, now, config)
    if err:
        return None, None, err
    goods = _refresh_goods_internal(
        commander_id, config, RefreshOptions(next_refresh_time=_next_daily_reset(now)),
    )[0]
    row = _get_state_row(commander_id)
    state = None
    if row:
        state = {"commander_id": row[0], "next_refresh_time": row[1]}
    return state, goods if state else None, None


def purchase(
    commander_id: int,
    goods_id: int,
    selected: list[PurchaseSelection],
    now: datetime,
    config: Config,
) -> tuple[list[PurchaseDrop], Optional[Exception]]:
    if goods_id == 0 or config is None:
        return None, InvalidPurchasePayload()

    _, _, err = refresh_if_needed(commander_id, now, config)
    if err:
        return None, err

    entry = _find_good(config, goods_id)
    if entry is None:
        return None, InvalidPurchasePayload()

    rewards, total_units, err = _resolve_purchase_rewards(entry, selected)
    if err:
        return None, err

    total_cost = entry.price * total_units

    store = get_default_store()

    buy_count = get_mini_game_shop_good_count(commander_id, goods_id)
    if buy_count is None:
        return None, InvalidPurchasePayload()
    limit = entry.goods_purchase_limit if entry.goods_purchase_limit and entry.goods_purchase_limit > 0 else 1
    remaining = limit - buy_count
    if remaining < total_units:
        return None, SoldOut()

    balance_row = store.fetchrow(
        "SELECT resources FROM commanders WHERE commander_id = $1",
        commander_id,
    )
    if balance_row is None:
        return None, InsufficientTickets()
    resources = json.loads(balance_row[0]) if isinstance(balance_row[0], str) else (balance_row[0] or {})
    current = resources.get(str(MINI_GAME_SHOP_TICKET_RESOURCE_ID), 0)
    if current < total_cost:
        return None, InsufficientTickets()

    increment_mini_game_shop_good_buy_count(commander_id, goods_id, total_units, limit)

    new_balance = current - total_cost
    resources[str(MINI_GAME_SHOP_TICKET_RESOURCE_ID)] = new_balance
    store.execute(
        "UPDATE commanders SET resources = $2::jsonb WHERE commander_id = $1",
        commander_id, json.dumps(resources),
    )

    for reward in rewards:
        if reward.type == DROP_TYPE_RESOURCE:
            rrow = store.fetchrow(
                "SELECT resources FROM commanders WHERE commander_id = $1",
                commander_id,
            )
            rsrc = json.loads(rrow[0]) if isinstance(rrow[0], str) else (rrow[0] or {})
            rsrc[str(reward.id)] = rsrc.get(str(reward.id), 0) + reward.number
            store.execute(
                "UPDATE commanders SET resources = $2::jsonb WHERE commander_id = $1",
                commander_id, json.dumps(rsrc),
            )
        elif reward.type == DROP_TYPE_ITEM:
            item_row = store.fetchrow(
                "SELECT id FROM items WHERE commander_id = $1 AND item_id = $2",
                commander_id, reward.id,
            )
            if item_row:
                store.execute(
                    "UPDATE items SET count = count + $3 WHERE commander_id = $1 AND item_id = $2",
                    commander_id, reward.id, reward.number,
                )
            else:
                store.execute(
                    "INSERT INTO items (commander_id, item_id, count) VALUES ($1, $2, $3)",
                    commander_id, reward.id, reward.number,
                )
        elif reward.type == DROP_TYPE_SHIP:
            for _ in range(reward.number):
                store.execute(
                    "INSERT INTO ships (commander_id, template_id, level) VALUES ($1, $2, 1) ON CONFLICT DO NOTHING",
                    commander_id, reward.id,
                )
        elif reward.type == DROP_TYPE_SKIN:
            for _ in range(reward.number):
                store.execute(
                    "INSERT INTO skins (commander_id, skin_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    commander_id, reward.id,
                )
        else:
            return None, UnsupportedReward()

    return rewards, None


def load_goods(commander_id: int) -> list[dict]:
    return _load_goods_internal(commander_id)


def _get_state_row(commander_id: int):
    state = get_mini_game_shop_state(commander_id)
    if state is None:
        return None
    return (state["commander_id"], state["next_refresh_time"])


def _load_goods_internal(commander_id: int) -> list[dict]:
    return list_mini_game_shop_goods(commander_id)


def _save_goods(commander_id: int, goods: list[dict], next_refresh_time: int):
    refresh_mini_game_shop_goods(commander_id, goods, next_refresh_time)



def _build_goods(commander_id: int, config: Config) -> list[dict]:
    if config is None:
        return []
    # `count` is the buy count (already purchased). The client derives the
    # remaining stock as (goods_purchase_limit - count), so start at 0.
    return [
        {
            "commander_id": commander_id,
            "goods_id": entry.id,
            "count": 0,
        }
        for entry in config.goods
    ]


def _find_good(config: Config, goods_id: int) -> Optional[shopEntry]:
    if config is None:
        return None
    for good in config.goods:
        if good.id == goods_id:
            return good
    return None


def _resolve_purchase_rewards(
    entry: shopEntry, selected: list[PurchaseSelection]
) -> tuple[list[PurchaseDrop], int, Optional[Exception]]:
    if not selected:
        return [], 0, InvalidPurchasePayload()

    allowed = set(g for g in entry.goods if g != 0)

    reward_units = {}
    total_units = 0
    for pick in selected:
        if pick.id == 0 or pick.num == 0:
            return [], 0, InvalidPurchasePayload()
        if allowed and pick.id not in allowed:
            return [], 0, InvalidPurchasePayload()
        total_units += pick.num
        reward_units[pick.id] = reward_units.get(pick.id, 0) + pick.num

    if total_units == 0:
        return [], 0, InvalidPurchasePayload()

    reward_multiplier = entry.num if entry.num > 0 else 1
    reward_ids = sorted(reward_units.keys())
    rewards = [
        PurchaseDrop(type=entry.drop_type, id=rid, number=reward_units[rid] * reward_multiplier)
        for rid in reward_ids
    ]
    return rewards, total_units, None


def _is_within_time(now: datetime, ranges: list) -> bool:
    if not ranges:
        return True
    current = now.astimezone(timezone.utc)
    for window in ranges:
        if not isinstance(window, list) or len(window) != 2:
            continue
        start_parts = window[0]
        end_parts = window[1]
        if not isinstance(start_parts, (list, tuple)) or len(start_parts) != 3:
            continue
        if not isinstance(end_parts, (list, tuple)) or len(end_parts) != 3:
            continue
        start = _time_from_config(start_parts)
        end = _time_from_config(end_parts)
        if start is not None and end is not None:
            if not (current < start) and not (current > end):
                return True
    return False


def _time_from_config(parts: list) -> Optional[datetime]:
    if parts[0] == 0 and parts[1] == 0 and parts[2] == 0:
        return None
    return datetime(parts[0], parts[1], parts[2], 0, 0, 0, 0, tzinfo=timezone.utc)


def _next_daily_reset(now: datetime) -> int:
    from src.shopreset.framework import daily_window
    return int(daily_window(now).end.timestamp())


_refresh_goods_internal = refresh_goods
