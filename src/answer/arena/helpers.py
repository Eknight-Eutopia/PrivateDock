import json
from typing import Optional

from src.db.store import get_default_store
from src.orm.config_entry import fetch_config_entries_data
from src.logger.logger import log_event, LOG_LEVEL_ERROR


class ShopTemplate:
    def __init__(self, data: dict):
        self.commodity_list_1 = data.get("commodity_list_1", [])
        self.commodity_list_2 = data.get("commodity_list_2", [])
        self.commodity_list_3 = data.get("commodity_list_3", [])
        self.commodity_list_4 = data.get("commodity_list_4", [])
        self.commodity_list_5 = data.get("commodity_list_5", [])
        self.commodity_list_common = data.get("commodity_list_common", [])
        self.refresh_price = data.get("refresh_price", [])


class ArenaShopConfig:
    def __init__(self, template: ShopTemplate):
        self.template = template


def load_config() -> Optional[ArenaShopConfig]:
    rows = fetch_config_entries_data("ShareCfg/arena_data_shop.json")
    if not rows:
        return ArenaShopConfig(ShopTemplate({}))
    data = rows[0]
    if isinstance(data, str):
        data = json.loads(data)
    return ArenaShopConfig(ShopTemplate(data if isinstance(data, dict) else {}))


def ensure_state(commander_id: int, now_unix: int):
    store = get_default_store()
    row = store.fetchrow(
        "SELECT commander_id, flash_count, last_refresh_time, next_flash_time FROM arena_shop_states WHERE commander_id = $1",
        commander_id
    )
    if row is None:
        next_flash = next_daily_reset(now_unix)
        store.execute(
            "INSERT INTO arena_shop_states (commander_id, flash_count, last_refresh_time, next_flash_time) VALUES ($1, 0, $2, $3)",
            commander_id, now_unix, next_flash
        )
        return {"commander_id": commander_id, "flash_count": 0, "last_refresh_time": now_unix, "next_flash_time": next_flash}
    return {"commander_id": row[0], "flash_count": row[1], "last_refresh_time": row[2], "next_flash_time": row[3]}


def refresh_if_needed(commander_id: int, now_unix: int):
    state = ensure_state(commander_id, now_unix)
    if now_unix >= state["next_flash_time"]:
        next_flash = next_daily_reset(now_unix)
        store = get_default_store()
        store.execute(
            "UPDATE arena_shop_states SET flash_count = 0, last_refresh_time = $1, next_flash_time = $2 WHERE commander_id = $3",
            now_unix, next_flash, commander_id
        )
        state["flash_count"] = 0
        state["last_refresh_time"] = now_unix
        state["next_flash_time"] = next_flash
        # A fresh daily flash resets the per-item purchase counts.
        clear_arena_buy_counts(commander_id)
    return state


def refresh_shop(commander_id: int, now_unix: int, config: Optional[ArenaShopConfig]):
    state = ensure_state(commander_id, now_unix)
    if config is None:
        return state, [], 0
    refresh_count = state["flash_count"] + 1
    if refresh_count > len(config.template.refresh_price):
        return state, [], 0
    cost = config.template.refresh_price[refresh_count - 1]
    state["flash_count"] += 1
    state["last_refresh_time"] = now_unix
    state["next_flash_time"] = next_daily_reset(now_unix)
    store = get_default_store()
    store.execute(
        "UPDATE arena_shop_states SET flash_count = $1, last_refresh_time = $2, next_flash_time = $3 WHERE commander_id = $4",
        state["flash_count"], now_unix, state["next_flash_time"], commander_id
    )
    # A re-roll replaces the goods, so reset the per-item purchase counts.
    clear_arena_buy_counts(commander_id)
    shop_list = build_shop_list(state["flash_count"], config, {})
    return state, shop_list, cost


def build_shop_list(flash_count: int, config: ArenaShopConfig,
                    buy_counts: Optional[dict] = None):
    if config is None:
        return []
    if buy_counts is None:
        buy_counts = {}
    template = config.template
    if flash_count == 0:
        tier = template.commodity_list_1
    elif flash_count == 1:
        tier = template.commodity_list_2
    elif flash_count == 2:
        tier = template.commodity_list_3
    elif flash_count == 3:
        tier = template.commodity_list_4
    elif flash_count == 4:
        tier = template.commodity_list_5
    else:
        tier = []
    entries = list(tier)
    if template.commodity_list_common:
        entries.extend(template.commodity_list_common)
    from src.protobuf import protobuf
    result = []
    for entry in entries:
        if len(entry) < 2:
            continue
        shop = protobuf.ARENASHOP()
        shop.shop_id = entry[0]
        # `count` is the per-item purchase count (buyCount). The client marks a
        # MeritorousShop item sold out when buyCount > 0, so we send the real
        # purchased count (0 until bought), NOT the config limit (entry[1]).
        shop.count = int(buy_counts.get(entry[0], 0) or 0)
        result.append(shop)
    return result


def load_arena_buy_counts(commander_id: int) -> dict:
    store = get_default_store()
    if store is None:
        return {}
    try:
        rows = store.fetch(
            "SELECT shop_id, buy_count FROM arena_shop_goods WHERE commander_id = $1",
            commander_id,
        )
        return {int(r[0]): int(r[1]) for r in rows}
    except Exception:
        return {}


def save_arena_buy_count(commander_id: int, shop_id: int, buy_count: int):
    store = get_default_store()
    if store is None:
        return
    try:
        store.execute(
            "INSERT INTO arena_shop_goods (commander_id, shop_id, buy_count) "
            "VALUES ($1, $2, $3) "
            "ON CONFLICT (commander_id, shop_id) DO UPDATE SET buy_count = EXCLUDED.buy_count",
            commander_id, shop_id, buy_count,
        )
    except Exception as e:
        log_event("ArenaShop", "SaveBuyCount", f"failed: {e}", LOG_LEVEL_ERROR)


def clear_arena_buy_counts(commander_id: int):
    store = get_default_store()
    if store is None:
        return
    try:
        store.execute(
            "DELETE FROM arena_shop_goods WHERE commander_id = $1", commander_id
        )
    except Exception as e:
        log_event("ArenaShop", "ClearBuyCount", f"failed: {e}", LOG_LEVEL_ERROR)


def next_daily_reset(now_unix: int) -> int:
    import datetime
    from src.shopreset.framework import daily_window
    now = datetime.datetime.fromtimestamp(now_unix, tz=datetime.timezone.utc)
    return int(daily_window(now).end.timestamp())


def has_enough_resource(commander_id: int, resource_type: int, amount: int) -> bool:
    from src.orm.resource import has_enough_resource as _has
    return _has(commander_id, resource_type, amount)


def consume_resource(commander_id: int, resource_type: int, amount: int):
    from src.orm.resource import consume_resource as _consume
    _consume(commander_id, resource_type, amount)
