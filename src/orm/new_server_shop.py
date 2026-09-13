from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


from src.db.session import get_session, get_sync_session
from src.orm.new_server_shop_state_table import NewServerShopStateTable


@dataclass
class NewServerShopGoodsState:
    id: int = 0
    count: int = 0
    bought_record: list = field(default_factory=list)


@dataclass
class NewServerShopState:
    commander_id: int = 0
    activity_id: int = 0
    goods: list[NewServerShopGoodsState] = field(default_factory=list)


def _goods_to_json(goods: list[NewServerShopGoodsState]) -> str:
    return json.dumps([
        {"id": g.id, "count": g.count, "bought_record": g.bought_record or []}
        for g in goods
    ])


def _goods_from_json(data) -> list[NewServerShopGoodsState]:
    if data is None:
        return []
    raw = data if isinstance(data, list) else json.loads(data) if isinstance(data, str) else []
    result = []
    for item in raw:
        g = NewServerShopGoodsState(
            id=int(item.get("id", 0)),
            count=int(item.get("count", 0)),
            bought_record=list(item.get("bought_record", []) or []),
        )
        if g.bought_record is None:
            g.bought_record = []
        result.append(g)
    return result


async def get_new_server_shop_state(commander_id: int, activity_id: int) -> Optional[NewServerShopState]:
    async with get_session() as s:
        row = await s.get(NewServerShopStateTable, (commander_id, activity_id))
        if row is None:
            return None
        state = NewServerShopState(
            commander_id=row.commander_id,
            activity_id=row.activity_id,
            goods=_goods_from_json(row.goods),
        )
        return state


async def upsert_new_server_shop_state(state: NewServerShopState) -> None:
    async with get_session() as s:
        row = await s.get(NewServerShopStateTable, (state.commander_id, state.activity_id))
        if row is None:
            row = NewServerShopStateTable(
                commander_id=state.commander_id,
                activity_id=state.activity_id,
                goods=_goods_to_json(state.goods),
            )
            s.add(row)
        else:
            row.goods = _goods_to_json(state.goods)
        await s.commit()


# ── Sync CRUD ──


def _sync_get_new_server_shop_state(commander_id: int, activity_id: int) -> Optional[NewServerShopState]:
    with get_sync_session() as s:
        row = s.get(NewServerShopStateTable, (commander_id, activity_id))
        if row is None:
            return None
        return NewServerShopState(
            commander_id=row.commander_id,
            activity_id=row.activity_id,
            goods=_goods_from_json(row.goods),
        )


def _sync_upsert_new_server_shop_state(state: NewServerShopState):
    with get_sync_session() as s:
        row = s.get(NewServerShopStateTable, (state.commander_id, state.activity_id))
        if row is None:
            row = NewServerShopStateTable(
                commander_id=state.commander_id,
                activity_id=state.activity_id,
                goods=_goods_to_json(state.goods),
            )
            s.add(row)
        else:
            row.goods = _goods_to_json(state.goods)
        s.commit()

get_new_server_shop_state = _sync_get_new_server_shop_state
upsert_new_server_shop_state = _sync_upsert_new_server_shop_state
