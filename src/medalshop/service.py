from __future__ import annotations
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.orm.config_entry import fetch_config_entries_data
from src.orm.medal_shop import (
    create_medal_shop_state,
    get_medal_shop_state,
    list_medal_shop_goods,
    refresh_medal_shop_goods,
)
from src.shopreset.framework import monthly_window as _monthly_window

MONTH_SHOP_CONFIG_CATEGORY = "ShareCfg/month_shop_template.json"
SHOP_TEMPLATE_CATEGORY = "ShareCfg/shop_template.json"

# Regeneration is a delete + inserts + state update; the lock serializes it in
# this process and _save_goods runs it in one DB transaction so concurrent
# writers (other threads/processes) can never leave a merged goods list.
_REFRESH_LOCK = threading.Lock()


@dataclass
class _MonthShopTemplate:
    id: int = 0
    honor_medal_shop_goods: list[int] = field(default_factory=list)


@dataclass
class _ShopTemplateEntry:
    id: int = 0
    goods_purchase_limit: int = 0


@dataclass
class Config:
    goods_ids: list[int] = field(default_factory=list)
    purchase_limit: dict[int, int] = field(default_factory=dict)


@dataclass
class RefreshOptions:
    next_refresh_time: int = 0


def load_config() -> Optional[Config]:
    return load_config_at(datetime.now(timezone.utc))


def load_config_at(now: datetime) -> Optional[Config]:
    month_rows = fetch_config_entries_data(MONTH_SHOP_CONFIG_CATEGORY)
    template = _select_month_template(month_rows, now)
    if template is None:
        return None

    purchase_limit = {}
    shop_rows = fetch_config_entries_data(SHOP_TEMPLATE_CATEGORY)
    for data in shop_rows:
        if not isinstance(data, dict):
            continue
        item = _ShopTemplateEntry(
            id=data.get("id", 0),
            goods_purchase_limit=data.get("goods_purchase_limit", 0),
        )
        if item.id == 0:
            continue
        purchase_limit[item.id] = item.goods_purchase_limit

    return Config(goods_ids=template, purchase_limit=purchase_limit)


def ensure_state(
    commander_id: int, now: datetime, config: Config
) -> tuple[dict, list[dict], Optional[Exception]]:
    state = get_medal_shop_state(commander_id)
    if state is None:
        next_time = _next_monthly_reset(now)
        create_medal_shop_state(commander_id, next_time)
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
    # The monthly refresh always writes exactly the month template's goods; a
    # longer list can only be corruption (or a merged interleaved write), so
    # heal it on fetch.
    expected = len(config.goods_ids) if config else 0
    if (now.timestamp() >= state["next_refresh_time"] or len(goods) == 0
            or (expected > 0 and len(goods) > expected)):
        goods = _refresh_goods_internal(
            commander_id, config, RefreshOptions(next_refresh_time=_next_monthly_reset(now)),
        )[0]
        refreshed_state = get_medal_shop_state(commander_id)
        if refreshed_state:
            state = refreshed_state
    return state, goods, None


def refresh_goods(
    commander_id: int, config: Config, options: RefreshOptions
) -> tuple[list[dict], Optional[Exception]]:
    with _REFRESH_LOCK:
        goods = _build_goods(commander_id, config)
        _save_goods(commander_id, goods, options.next_refresh_time)
    return goods, None


def load_goods(commander_id: int) -> list[dict]:
    return _load_goods_internal(commander_id)


def next_monthly_reset(now: datetime) -> int:
    return _next_monthly_reset(now)


def _load_goods_internal(commander_id: int) -> list[dict]:
    return list_medal_shop_goods(commander_id)


def _save_goods(commander_id: int, goods: list[dict], next_refresh_time: int):
    refresh_medal_shop_goods(commander_id, goods, next_refresh_time)


def _build_goods(commander_id: int, config: Config) -> list[dict]:
    if config is None or not config.goods_ids:
        return []
    return [
        {
            "commander_id": commander_id,
            "index": i + 1,
            "goods_id": gid,
            "count": config.purchase_limit.get(gid, 1) or 1,
        }
        for i, gid in enumerate(config.goods_ids)
    ]


def _next_monthly_reset(now: datetime) -> int:
    try:
        w = _monthly_window(now)
        return int(w.end.timestamp())
    except Exception:
        utc = now.astimezone(timezone.utc)
        next_month = datetime(utc.year, utc.month, 1, 0, 0, 0, 0, tzinfo=timezone.utc) + timedelta(days=32)
        next_month = next_month.replace(day=1)
        return int(next_month.timestamp())


def _select_month_template(rows: list, now: datetime) -> Optional[list[int]]:
    templates = []
    for row in rows:
        data_raw = row[0] if hasattr(row, '__getitem__') else row.data if hasattr(row, 'data') else row
        data = json.loads(data_raw) if isinstance(data_raw, str) else data_raw
        if isinstance(data, dict):
            if data.get("id", 0) != 0 or data.get("honormedal_shop_goods"):
                templates.append(_MonthShopTemplate(
                    id=data.get("id", 0),
                    honor_medal_shop_goods=data.get("honormedal_shop_goods", []),
                ))
                continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    templates.append(_MonthShopTemplate(
                        id=item.get("id", 0),
                        honor_medal_shop_goods=item.get("honormedal_shop_goods", []),
                    ))
    if not templates:
        return None

    try:
        w = _monthly_window(now)
        month = w.key % 100
    except Exception:
        month = now.astimezone(timezone.utc).month

    for t in templates:
        if t.id == month:
            return t.honor_medal_shop_goods

    templates.sort(key=lambda t: t.id)
    index = (month - 1) % len(templates)
    return templates[index].honor_medal_shop_goods


_refresh_goods_internal = refresh_goods
