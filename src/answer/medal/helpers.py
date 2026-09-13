import json
import time
from dataclasses import dataclass

from src.orm.config_entry import afetch_config_entries_data
from src.orm.medal_shop import (
    acreate_medal_shop_state,
    aget_medal_shop_next_refresh,
    alist_medal_shop_goods,
    arefresh_medal_shop_goods,
)

medalShopCurrencyItemID = 15001

medalShopPurchaseResultOK = 0
medalShopPurchaseResultInvalid = 1
medalShopPurchaseResultInsufficient = 2
medalShopPurchaseResultStock = 3
medalShopPurchaseResultStale = 4
medalShopPurchaseResultUnsupported = 5
medalShopPurchaseResultDBError = 6


@dataclass
class HonorMedalGoodsListEntry:
    id: int = 0
    group: int = 0
    price: int = 0
    goods: list = None
    goods_type: int = 0
    num: int = 0
    is_ship: int = 0
    goods_purchase_limit: int = 0


def contains_uint32(lst: list, value: int) -> bool:
    return value in lst


def _decode_config_data(raw) -> object:
    """config_entries.data normalizer.

    jsonb arrives as parsed objects on the psycopg2 sync path but as JSON
    TEXT on asyncpg and SQLite (the codebase contract), so every reader must
    accept both -- the bytes-only check silently let strings through and
    crashed the shop with 'str' object has no attribute 'get'."""
    if isinstance(raw, memoryview):
        raw = bytes(raw)
    if isinstance(raw, (bytes, bytearray, str)):
        try:
            return json.loads(raw)
        except Exception:
            return None
    return raw


async def load_honor_medal_goods_list_entry(shop_id: int) -> tuple:
    rows = await afetch_config_entries_data("ShareCfg/honormedal_goods_list.json")
    for data in rows:
        if data is None:
            continue
        if isinstance(data, list) and len(data) > 0:
            for entry in data:
                if isinstance(entry, dict) and entry.get("id") == shop_id:
                    return HonorMedalGoodsListEntry(
                        id=entry.get("id", 0),
                        group=entry.get("group", 0),
                        price=entry.get("price", 0),
                        goods=entry.get("goods", []),
                        goods_type=entry.get("goods_type", 0),
                        num=entry.get("num", 0),
                        is_ship=entry.get("is_ship", 0),
                        goods_purchase_limit=entry.get("goods_purchase_limit", 0),
                    ), True
            continue
        if isinstance(data, dict):
            if data.get("id") == shop_id:
                return HonorMedalGoodsListEntry(
                    id=data.get("id", 0),
                    group=data.get("group", 0),
                    price=data.get("price", 0),
                    goods=data.get("goods", []),
                    goods_type=data.get("goods_type", 0),
                    num=data.get("num", 0),
                    is_ship=data.get("is_ship", 0),
                    goods_purchase_limit=data.get("goods_purchase_limit", 0),
                ), True
    return None, False


async def load_config():
    month_category = "ShareCfg/month_shop_template.json"
    shop_category = "ShareCfg/honormedal_goods_list.json"
    month_rows = await afetch_config_entries_data(month_category)
    month_groups = await _select_month_template(month_rows)

    entries = []
    shop_rows = await afetch_config_entries_data(shop_category)
    for item in shop_rows:
        if item is None:
            continue
        entries.append(item)

    group_set = set(month_groups) if month_groups else set()
    goods_ids = []
    purchase_limit = {}
    for item in entries:
        if not group_set or item.get("group") in group_set:
            sid = item.get("id", 0)
            if sid:
                goods_ids.append(sid)
                purchase_limit[sid] = item.get("goods_purchase_limit", 0)
    return goods_ids, purchase_limit


async def _select_month_template(rows):
    templates = []
    for row in rows:
        data = _decode_config_data(row["data"]) if isinstance(row, dict) and "data" in row else row
        if data is None:
            continue
        if isinstance(data, dict):
            sid = data.get("id", 0)
            if sid != 0 or data.get("honormedal_shop_goods"):
                templates.append(data)
        elif isinstance(data, list):
            templates.extend(data)
    if not templates:
        return []
    now = time.gmtime()
    month = now.tm_mon
    for t in templates:
        if t.get("id") == month:
            return t.get("honormedal_shop_goods", [])
    templates.sort(key=lambda t: t.get("id", 0))
    index = (month - 1) % len(templates)
    return templates[index].get("honormedal_shop_goods", [])


async def ensure_state(commander_id: int, now: float, goods_ids: list, purchase_limit: dict) -> tuple:
    next_refresh = await aget_medal_shop_next_refresh(commander_id)
    if next_refresh is None:
        next_refresh = _next_monthly_reset(now)
        await acreate_medal_shop_state(commander_id, next_refresh)
        goods = await _refresh_goods(commander_id, goods_ids, purchase_limit, next_refresh)
        return next_refresh, goods
    goods = await _load_goods(commander_id)
    return next_refresh, goods


async def refresh_if_needed(commander_id: int, now: float, goods_ids: list, purchase_limit: dict) -> tuple:
    next_refresh, goods = await ensure_state(commander_id, now, goods_ids, purchase_limit)

    id_set = set(goods_ids)
    # Heal anything that cannot be a legitimate mid-period list: rows outside
    # the current template, or more rows than the template defines (the only
    # way a merged/corrupt list can sneak past the (commander_id, index) PK).
    stale = (goods_ids and (len(goods) > len(goods_ids)
                            or any(g.get("goods_id", 0) not in id_set for g in goods)))

    if now >= next_refresh or not goods or stale:
        next_refresh = _next_monthly_reset(now)
        goods = await _refresh_goods(commander_id, goods_ids, purchase_limit, next_refresh)
        refreshed = await aget_medal_shop_next_refresh(commander_id)
        next_refresh = refreshed if refreshed is not None else next_refresh
    return next_refresh, goods


async def _refresh_goods(commander_id: int, goods_ids: list, purchase_limit: dict, next_refresh: int) -> list:
    if not goods_ids:
        return []
    goods = []
    for i, gid in enumerate(goods_ids):
        # `count` is the REMAINING stock (limit - bought), NOT a buy count. The
        # client's MedalGoods.CanPurchase is `count > 0` and UpdateCnt decrements
        # it, so a fresh refresh starts each item at its per-period purchase limit.
        goods.append({
            "commander_id": commander_id,
            "index": i + 1,
            "goods_id": gid,
            "count": int(purchase_limit.get(gid, 1) or 1),
        })
    await arefresh_medal_shop_goods(commander_id, goods, next_refresh)
    return goods


async def _load_goods(commander_id: int) -> list:
    return await alist_medal_shop_goods(commander_id)


def _next_monthly_reset(now_ts: float) -> int:
    from datetime import datetime, timezone
    from src.shopreset.framework import monthly_window
    now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    return int(monthly_window(now).end.timestamp())


def build_medal_shop_goods(goods: list) -> list:
    from src.protobuf import protobuf
    result = []
    for g in goods:
        result.append(protobuf.GOODS_INFO_P16(id=g["goods_id"], count=g["count"]))
    return result
