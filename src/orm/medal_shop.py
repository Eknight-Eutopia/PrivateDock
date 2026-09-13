from __future__ import annotations

from typing import Any, Optional, Sequence

from src.db.store import get_default_store
from src.orm.medal_shop_good import MedalShopGood
from src.orm.medal_shop_state import MedalShopState


def _is_positive_count(result: Any) -> bool:
    try:
        return int(result) > 0
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# Medal Shop States
# --------------------------------------------------------------------------- #

def get_medal_shop_state(commander_id: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = store.fetchrow(
            "SELECT commander_id, next_refresh_time FROM medal_shop_states WHERE commander_id = $1",
            commander_id,
        )
        if row is None:
            return None
        return {"commander_id": row[0], "next_refresh_time": row[1]}
    except Exception:
        return None


async def aget_medal_shop_state(commander_id: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = await store.afetchrow(
            "SELECT commander_id, next_refresh_time FROM medal_shop_states WHERE commander_id = $1",
            commander_id,
        )
        if row is None:
            return None
        return {"commander_id": row[0], "next_refresh_time": row[1]}
    except Exception:
        return None


def get_medal_shop_next_refresh(commander_id: int) -> Optional[int]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = store.fetchrow(
            "SELECT next_refresh_time FROM medal_shop_states WHERE commander_id = $1",
            commander_id,
        )
        return row[0] if row is not None else None
    except Exception:
        return None


async def aget_medal_shop_next_refresh(commander_id: int) -> Optional[int]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = await store.afetchrow(
            "SELECT next_refresh_time FROM medal_shop_states WHERE commander_id = $1",
            commander_id,
        )
        return row[0] if row is not None else None
    except Exception:
        return None


def create_medal_shop_state(commander_id: int, next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute(
        "INSERT INTO medal_shop_states (commander_id, next_refresh_time) VALUES ($1, $2)",
        commander_id, next_refresh_time,
    )


async def acreate_medal_shop_state(commander_id: int, next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        "INSERT INTO medal_shop_states (commander_id, next_refresh_time) VALUES ($1, $2)",
        commander_id, next_refresh_time,
    )


def update_medal_shop_state(commander_id: int, next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute(
        "UPDATE medal_shop_states SET next_refresh_time = $2 WHERE commander_id = $1",
        commander_id, next_refresh_time,
    )


async def aupdate_medal_shop_state(commander_id: int, next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        "UPDATE medal_shop_states SET next_refresh_time = $2 WHERE commander_id = $1",
        commander_id, next_refresh_time,
    )


def upsert_medal_shop_state(commander_id: int, next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute(
        """
        INSERT INTO medal_shop_states (commander_id, next_refresh_time)
        VALUES ($1, $2)
        ON CONFLICT (commander_id) DO UPDATE SET next_refresh_time = EXCLUDED.next_refresh_time
        """,
        commander_id, next_refresh_time,
    )


async def aupsert_medal_shop_state(commander_id: int, next_refresh_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        """
        INSERT INTO medal_shop_states (commander_id, next_refresh_time)
        VALUES ($1, $2)
        ON CONFLICT (commander_id) DO UPDATE SET next_refresh_time = EXCLUDED.next_refresh_time
        """,
        commander_id, next_refresh_time,
    )


# --------------------------------------------------------------------------- #
# Medal Shop Goods
# --------------------------------------------------------------------------- #

def list_medal_shop_goods(commander_id: int) -> list[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return []
    try:
        rows = store.fetch(
            "SELECT commander_id, index, goods_id, count FROM medal_shop_goods WHERE commander_id = $1 ORDER BY index",
            commander_id,
        )
        return [
            {"commander_id": r[0], "index": r[1], "goods_id": r[2], "count": r[3]}
            for r in rows
        ]
    except Exception:
        return []


async def alist_medal_shop_goods(commander_id: int) -> list[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return []
    try:
        rows = await store.afetch(
            "SELECT commander_id, index, goods_id, count FROM medal_shop_goods WHERE commander_id = $1 ORDER BY index",
            commander_id,
        )
        return [
            {"commander_id": r[0], "index": r[1], "goods_id": r[2], "count": r[3]}
            for r in rows
        ]
    except Exception:
        return []


def get_medal_shop_good_by_goods_id(commander_id: int, goods_id: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = store.fetchrow(
            'SELECT "index", count FROM medal_shop_goods WHERE commander_id = $1 AND goods_id = $2',
            commander_id, goods_id,
        )
        if row is None:
            return None
        return {"index": row[0], "count": row[1]}
    except Exception:
        return None


async def aget_medal_shop_good_by_goods_id(commander_id: int, goods_id: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = await store.afetchrow(
            'SELECT "index", count FROM medal_shop_goods WHERE commander_id = $1 AND goods_id = $2',
            commander_id, goods_id,
        )
        if row is None:
            return None
        return {"index": row[0], "count": row[1]}
    except Exception:
        return None


def get_medal_shop_good_by_index(commander_id: int, index: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = store.fetchrow(
            'SELECT goods_id, count FROM medal_shop_goods WHERE commander_id = $1 AND "index" = $2',
            commander_id, index,
        )
        if row is None:
            return None
        return {"goods_id": row[0], "count": row[1]}
    except Exception:
        return None


async def aget_medal_shop_good_by_index(commander_id: int, index: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = await store.afetchrow(
            'SELECT goods_id, count FROM medal_shop_goods WHERE commander_id = $1 AND "index" = $2',
            commander_id, index,
        )
        if row is None:
            return None
        return {"goods_id": row[0], "count": row[1]}
    except Exception:
        return None


def create_medal_shop_good(commander_id: int, index: int, goods_id: int, count: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute(
        'INSERT INTO medal_shop_goods (commander_id, "index", goods_id, count) VALUES ($1, $2, $3, $4)',
        commander_id, index, goods_id, count,
    )


async def acreate_medal_shop_good(commander_id: int, index: int, goods_id: int, count: int) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        'INSERT INTO medal_shop_goods (commander_id, "index", goods_id, count) VALUES ($1, $2, $3, $4)',
        commander_id, index, goods_id, count,
    )


def delete_medal_shop_goods(commander_id: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute("DELETE FROM medal_shop_goods WHERE commander_id = $1", commander_id)


async def adelete_medal_shop_goods(commander_id: int) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute("DELETE FROM medal_shop_goods WHERE commander_id = $1", commander_id)


def delete_medal_shop_good_by_index(commander_id: int, index: int) -> bool:
    store = get_default_store()
    if store is None:
        return False
    try:
        res = store.execute(
            'DELETE FROM medal_shop_goods WHERE commander_id = $1 AND "index" = $2',
            commander_id, index,
        )
        return _is_positive_count(res)
    except Exception:
        return False


async def adelete_medal_shop_good_by_index(commander_id: int, index: int) -> bool:
    store = get_default_store()
    if store is None:
        return False
    try:
        res = await store.aexecute(
            'DELETE FROM medal_shop_goods WHERE commander_id = $1 AND "index" = $2',
            commander_id, index,
        )
        return _is_positive_count(res)
    except Exception:
        return False


def decrement_medal_shop_good_count(commander_id: int, index: int, count: int) -> bool:
    store = get_default_store()
    if store is None:
        return False
    try:
        res = store.execute(
            'UPDATE medal_shop_goods SET count = count - $3 WHERE commander_id = $1 AND "index" = $2 AND count >= $3',
            commander_id, index, count,
        )
        return _is_positive_count(res)
    except Exception:
        return False


async def adecrement_medal_shop_good_count(commander_id: int, index: int, count: int) -> bool:
    store = get_default_store()
    if store is None:
        return False
    try:
        res = await store.aexecute(
            'UPDATE medal_shop_goods SET count = count - $3 WHERE commander_id = $1 AND "index" = $2 AND count >= $3',
            commander_id, index, count,
        )
        return _is_positive_count(res)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Atomic Refresh Operations
# --------------------------------------------------------------------------- #

def refresh_medal_shop_goods(
    commander_id: int, goods: Sequence[dict[str, Any]], next_refresh_time: int
) -> None:
    store = get_default_store()
    if store is None:
        return
    with store.sync_transaction() as tx:
        tx.execute("DELETE FROM medal_shop_goods WHERE commander_id = $1", commander_id)
        for g in goods:
            tx.execute(
                'INSERT INTO medal_shop_goods (commander_id, "index", goods_id, count) VALUES ($1, $2, $3, $4)',
                commander_id, g["index"], g["goods_id"], g["count"],
            )
        tx.execute(
            "UPDATE medal_shop_states SET next_refresh_time = $2 WHERE commander_id = $1",
            commander_id, next_refresh_time,
        )


async def arefresh_medal_shop_goods(
    commander_id: int, goods: Sequence[dict[str, Any]], next_refresh_time: int
) -> None:
    store = get_default_store()
    if store is None:
        return
    async with store.atransaction() as tx:
        await tx.execute("DELETE FROM medal_shop_goods WHERE commander_id = $1", commander_id)
        for g in goods:
            await tx.execute(
                'INSERT INTO medal_shop_goods (commander_id, "index", goods_id, count) VALUES ($1, $2, $3, $4)',
                g.get("commander_id", commander_id), g["index"], g["goods_id"], g["count"],
            )
        await tx.execute(
            "UPDATE medal_shop_states SET next_refresh_time = $2 WHERE commander_id = $1",
            commander_id, next_refresh_time,
        )


__all__ = [
    "MedalShopState",
    "MedalShopGood",
    "get_medal_shop_state",
    "aget_medal_shop_state",
    "get_medal_shop_next_refresh",
    "aget_medal_shop_next_refresh",
    "create_medal_shop_state",
    "acreate_medal_shop_state",
    "update_medal_shop_state",
    "aupdate_medal_shop_state",
    "upsert_medal_shop_state",
    "aupsert_medal_shop_state",
    "list_medal_shop_goods",
    "alist_medal_shop_goods",
    "get_medal_shop_good_by_goods_id",
    "aget_medal_shop_good_by_goods_id",
    "get_medal_shop_good_by_index",
    "aget_medal_shop_good_by_index",
    "create_medal_shop_good",
    "acreate_medal_shop_good",
    "delete_medal_shop_goods",
    "adelete_medal_shop_goods",
    "delete_medal_shop_good_by_index",
    "adelete_medal_shop_good_by_index",
    "decrement_medal_shop_good_count",
    "adecrement_medal_shop_good_count",
    "refresh_medal_shop_goods",
    "arefresh_medal_shop_goods",
]
