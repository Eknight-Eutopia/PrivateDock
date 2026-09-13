from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import BigInteger, JSON, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


@dataclass
class EducateShopGoodsState:
    id: int = 0
    num: int = 0


class EducateShopStateTable(Base):
    __tablename__ = "educate_shop_states"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    refresh_key: Mapped[int] = mapped_column(BigInteger, default=0)
    goods: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


@dataclass
class EducateShopState:
    commander_id: int = 0
    shop_id: int = 0
    refresh_key: int = 0
    goods: list[EducateShopGoodsState] = field(default_factory=list)


def _goods_from_json(data: Optional[list]) -> list[EducateShopGoodsState]:
    if not data:
        return []
    return [EducateShopGoodsState(id=g.get("id", 0), num=g.get("num", 0)) for g in data]


def _goods_to_json(goods: list[EducateShopGoodsState]) -> list[dict]:
    return [{"id": g.id, "num": g.num} for g in goods]


def get_educate_shop_state(commander_id: int, shop_id: int) -> Optional[EducateShopState]:
    with get_sync_session() as session:
        row = session.execute(
            select(EducateShopStateTable).where(
                EducateShopStateTable.commander_id == commander_id,
                EducateShopStateTable.shop_id == shop_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return EducateShopState(
            commander_id=row.commander_id,
            shop_id=row.shop_id,
            refresh_key=row.refresh_key,
            goods=_goods_from_json(row.goods),
        )


def upsert_educate_shop_state(state: EducateShopState) -> None:
    goods = state.goods if state.goods is not None else []
    with get_sync_session() as session:
        existing = session.execute(
            select(EducateShopStateTable).where(
                EducateShopStateTable.commander_id == state.commander_id,
                EducateShopStateTable.shop_id == state.shop_id,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = EducateShopStateTable(
                commander_id=state.commander_id,
                shop_id=state.shop_id,
                refresh_key=state.refresh_key,
                goods=_goods_to_json(goods),
            )
            session.add(existing)
        else:
            existing.refresh_key = state.refresh_key
            existing.goods = _goods_to_json(goods)
        session.commit()


def list_educate_shop_states(commander_id: int) -> list[EducateShopState]:
    with get_sync_session() as session:
        rows = (
            session.execute(
                select(EducateShopStateTable)
                .where(EducateShopStateTable.commander_id == commander_id)
                .order_by(EducateShopStateTable.shop_id)
            )
            .scalars()
            .all()
        )
        return [
            EducateShopState(
                commander_id=r.commander_id,
                shop_id=r.shop_id,
                refresh_key=r.refresh_key,
                goods=_goods_from_json(r.goods),
            )
            for r in rows
        ]
