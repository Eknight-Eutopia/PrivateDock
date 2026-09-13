from __future__ import annotations

from typing import Any, Optional, Sequence

from src.db.store import get_default_store
from src.orm.mini_game_shop_good import MiniGameShopGood
from src.orm.mini_game_shop_state import MiniGameShopState


def get_mini_game_shop_state(commander_id: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = store.fetchrow(
            "SELECT commander_id, next_refresh_time FROM mini_game_shop_states WHERE commander_id = $1",
            commander_id,
        )
        if row is None:
            return None
        return {"commander_id": row[0], "next_refresh_time": row[1]}
    except Exception:
        return None


async def aget_mini_game_shop_state(commander_id: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = await store.afetchrow(
            "SELECT commander_id, next_refresh_time FROM mini_game_shop_states WHERE commander_id = $1",
            commander_id,
        )
        if row is None:
            return None
        return {"commander_id": row[0], "next_refresh_time": row[1]}
    except Exception:
        return None


def create_mini_game_shop_state(commander_id: int, next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute(
        "INSERT INTO mini_game_shop_states (commander_id, next_refresh_time) VALUES ($1, $2)",
        commander_id, next_refresh_time,
    )


async def acreate_mini_game_shop_state(commander_id: int, next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        "INSERT INTO mini_game_shop_states (commander_id, next_refresh_time) VALUES ($1, $2)",
        commander_id, next_refresh_time,
    )


def update_mini_game_shop_state(commander_id: int, next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute(
        "UPDATE mini_game_shop_states SET next_refresh_time = $2 WHERE commander_id = $1",
        commander_id, next_refresh_time,
    )


async def aupdate_mini_game_shop_state(commander_id: int, next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        "UPDATE mini_game_shop_states SET next_refresh_time = $2 WHERE commander_id = $1",
        commander_id, next_refresh_time,
    )


def list_mini_game_shop_goods(commander_id: int) -> list[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return []
    try:
        rows = store.fetch(
            "SELECT commander_id, goods_id, count FROM mini_game_shop_goods WHERE commander_id = $1 ORDER BY goods_id ASC",
            commander_id,
        )
        return [{"commander_id": r[0], "goods_id": r[1], "count": r[2]} for r in rows]
    except Exception:
        return []


async def alist_mini_game_shop_goods(commander_id: int) -> list[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return []
    try:
        rows = await store.afetch(
            "SELECT commander_id, goods_id, count FROM mini_game_shop_goods WHERE commander_id = $1 ORDER BY goods_id ASC",
            commander_id,
        )
        return [{"commander_id": r[0], "goods_id": r[1], "count": r[2]} for r in rows]
    except Exception:
        return []


def get_mini_game_shop_good_count(commander_id: int, goods_id: int) -> Optional[int]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = store.fetchrow(
            "SELECT count FROM mini_game_shop_goods WHERE commander_id = $1 AND goods_id = $2",
            commander_id, goods_id,
        )
        return row[0] if row else None
    except Exception:
        return None


async def aget_mini_game_shop_good_count(commander_id: int, goods_id: int) -> Optional[int]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = await store.afetchrow(
            "SELECT count FROM mini_game_shop_goods WHERE commander_id = $1 AND goods_id = $2",
            commander_id, goods_id,
        )
        return row[0] if row else None
    except Exception:
        return None


def create_mini_game_shop_good(commander_id: int, goods_id: int, count: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute(
        "INSERT INTO mini_game_shop_goods (commander_id, goods_id, count) VALUES ($1, $2, $3)",
        commander_id, goods_id, count,
    )


async def acreate_mini_game_shop_good(commander_id: int, goods_id: int, count: int) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        "INSERT INTO mini_game_shop_goods (commander_id, goods_id, count) VALUES ($1, $2, $3)",
        commander_id, goods_id, count,
    )


def delete_mini_game_shop_goods(commander_id: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute("DELETE FROM mini_game_shop_goods WHERE commander_id = $1", commander_id)


async def adelete_mini_game_shop_goods(commander_id: int) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute("DELETE FROM mini_game_shop_goods WHERE commander_id = $1", commander_id)


def refresh_mini_game_shop_goods(commander_id: int, goods: Sequence[dict[str, Any]], next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    with store.sync_transaction() as tx:
        tx.execute("DELETE FROM mini_game_shop_goods WHERE commander_id = $1", commander_id)
        for g in goods:
            tx.execute(
                "INSERT INTO mini_game_shop_goods (commander_id, goods_id, count) VALUES ($1, $2, $3)",
                commander_id, g["goods_id"], g["count"],
            )
        tx.execute(
            "UPDATE mini_game_shop_states SET next_refresh_time = $2 WHERE commander_id = $1",
            commander_id, next_refresh_time,
        )


def increment_mini_game_shop_good_buy_count(commander_id: int, goods_id: int, count: int, limit: int) -> bool:
    store = get_default_store()
    if store is None:
        return False
    try:
        store.execute(
            "UPDATE mini_game_shop_goods SET count = count + $3 WHERE commander_id = $1 AND goods_id = $2 AND count + $3 <= $4",
            commander_id, goods_id, count, limit,
        )
        return True
    except Exception:
        return False


async def aincrement_mini_game_shop_good_buy_count(commander_id: int, goods_id: int, count: int, limit: int) -> bool:
    store = get_default_store()
    if store is None:
        return False
    try:
        await store.aexecute(
            "UPDATE mini_game_shop_goods SET count = count + $3 WHERE commander_id = $1 AND goods_id = $2 AND count + $3 <= $4",
            commander_id, goods_id, count, limit,
        )
        return True
    except Exception:
        return False
